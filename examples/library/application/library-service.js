/**
 * Library Application Service
 *
 * Orchestrates use cases:
 * - Adding books to the library
 * - Creating patrons
 * - Placing holds
 * - Checking out books
 * - Returning books
 *
 * Uses Event Sourcing with optimistic concurrency
 */

import { EventStore } from '../infrastructure/event-store.js';
import { Book } from '../domain/book.js';
import { Patron } from '../domain/patron.js';
import { PatronType, HoldType, BookType, BookState } from '../domain/events.js';
import { NO_STREAM, ANY } from '@kurrent/kurrentdb-client';

// Default hold duration: 7 days
const DEFAULT_HOLD_DURATION_DAYS = 7;

export class LibraryService {
    constructor(eventStore = new EventStore()) {
        this.eventStore = eventStore;
    }

    /**
     * Add a new book to the library
     */
    async addBook(bookId, isbn, title, bookType, libraryBranchId) {
        const streamName = Book.getStreamName(bookId);

        // Check if book already exists
        const exists = await this.eventStore.streamExists(streamName);
        if (exists) {
            return { success: false, error: 'Book already exists' };
        }

        const { book, event } = Book.create(bookId, isbn, title, bookType, libraryBranchId);

        const result = await this.eventStore.appendToStream(
            streamName,
            [event],
            NO_STREAM
        );

        if (!result.success) {
            return result;
        }

        return {
            success: true,
            bookId,
            message: `Book "${title}" added to library branch ${libraryBranchId}`,
        };
    }

    /**
     * Create a new patron
     */
    async createPatron(patronId, patronType, name, email) {
        const streamName = Patron.getStreamName(patronId);

        // Check if patron already exists
        const exists = await this.eventStore.streamExists(streamName);
        if (exists) {
            return { success: false, error: 'Patron already exists' };
        }

        const { patron, event } = Patron.create(patronId, patronType, name, email);

        const result = await this.eventStore.appendToStream(
            streamName,
            [event],
            NO_STREAM
        );

        if (!result.success) {
            return result;
        }

        return {
            success: true,
            patronId,
            message: `Patron "${name}" created as ${patronType}`,
        };
    }

    /**
     * Place a hold on a book
     */
    async placeHold(bookId, patronId, holdType = HoldType.CLOSED_ENDED, holdDurationDays = DEFAULT_HOLD_DURATION_DAYS) {
        // Load book aggregate
        const bookResult = await this.loadBook(bookId);
        if (!bookResult.success) {
            return bookResult;
        }
        const { book, revision: bookRevision } = bookResult;

        // Load patron aggregate
        const patronResult = await this.loadPatron(patronId);
        if (!patronResult.success) {
            return patronResult;
        }
        const { patron } = patronResult;

        // Check patron's eligibility
        const eligibility = patron.canPlaceHoldAt(book.libraryBranchId, book.bookType);
        if (!eligibility.allowed) {
            return { success: false, error: eligibility.reason };
        }

        // Calculate hold expiration for closed-ended holds
        let holdTill = null;
        if (holdType === HoldType.CLOSED_ENDED) {
            const expiration = new Date();
            expiration.setDate(expiration.getDate() + holdDurationDays);
            holdTill = expiration.toISOString();
        }

        // Attempt to place hold on book
        const holdResult = book.placeOnHold(patronId, patron.patronType, holdType, holdTill);
        if (!holdResult.success) {
            return holdResult;
        }

        // Persist the event
        const streamName = Book.getStreamName(bookId);
        const appendResult = await this.eventStore.appendToStream(
            streamName,
            [holdResult.event],
            BigInt(bookRevision)
        );

        if (!appendResult.success) {
            return appendResult;
        }

        return {
            success: true,
            message: `Hold placed on book "${book.title}" by patron "${patron.name}"`,
            holdType,
            holdTill,
        };
    }

    /**
     * Cancel a hold
     */
    async cancelHold(bookId, patronId, reason = 'Canceled by patron') {
        const bookResult = await this.loadBook(bookId);
        if (!bookResult.success) {
            return bookResult;
        }
        const { book, revision } = bookResult;

        const cancelResult = book.cancelHold(patronId, reason);
        if (!cancelResult.success) {
            return cancelResult;
        }

        const streamName = Book.getStreamName(bookId);
        const appendResult = await this.eventStore.appendToStream(
            streamName,
            [cancelResult.event],
            BigInt(revision)
        );

        if (!appendResult.success) {
            return appendResult;
        }

        return {
            success: true,
            message: `Hold canceled on book "${book.title}"`,
            reason,
        };
    }

    /**
     * Checkout a book (must be on hold by the same patron)
     */
    async checkout(bookId, patronId) {
        const bookResult = await this.loadBook(bookId);
        if (!bookResult.success) {
            return bookResult;
        }
        const { book, revision } = bookResult;

        const checkoutResult = book.checkout(patronId);
        if (!checkoutResult.success) {
            return checkoutResult;
        }

        const streamName = Book.getStreamName(bookId);
        const appendResult = await this.eventStore.appendToStream(
            streamName,
            [checkoutResult.event],
            BigInt(revision)
        );

        if (!appendResult.success) {
            return appendResult;
        }

        return {
            success: true,
            message: `Book "${book.title}" checked out`,
            dueDate: checkoutResult.event.data.dueDate,
        };
    }

    /**
     * Return a book
     */
    async returnBook(bookId, patronId) {
        const bookResult = await this.loadBook(bookId);
        if (!bookResult.success) {
            return bookResult;
        }
        const { book, revision } = bookResult;

        const returnResult = book.returnBook(patronId);
        if (!returnResult.success) {
            return returnResult;
        }

        const streamName = Book.getStreamName(bookId);
        const appendResult = await this.eventStore.appendToStream(
            streamName,
            [returnResult.event],
            BigInt(revision)
        );

        if (!appendResult.success) {
            return appendResult;
        }

        return {
            success: true,
            message: `Book "${book.title}" returned`,
        };
    }

    /**
     * Get book details
     */
    async getBook(bookId) {
        const result = await this.loadBook(bookId);
        if (!result.success) {
            return result;
        }

        const { book } = result;
        return {
            success: true,
            book: {
                bookId: book.bookId,
                isbn: book.isbn,
                title: book.title,
                bookType: book.bookType,
                libraryBranchId: book.libraryBranchId,
                state: book.state,
                holdingPatronId: book.holdingPatronId,
                holdTill: book.holdTill,
                checkedOutBy: book.checkedOutBy,
                dueDate: book.dueDate,
            },
        };
    }

    /**
     * Get patron details
     */
    async getPatron(patronId) {
        const result = await this.loadPatron(patronId);
        if (!result.success) {
            return result;
        }

        return {
            success: true,
            patron: result.patron.getSummary(),
        };
    }

    /**
     * Load book aggregate from event store
     */
    async loadBook(bookId) {
        const streamName = Book.getStreamName(bookId);
        const result = await this.eventStore.readStream(streamName);

        if (result.notFound || result.events.length === 0) {
            return { success: false, error: `Book not found: ${bookId}` };
        }

        const book = Book.fromEvents(result.events);
        const revision = await this.eventStore.getStreamRevision(streamName);

        return { success: true, book, revision };
    }

    /**
     * Load patron aggregate from event store
     */
    async loadPatron(patronId) {
        const streamName = Patron.getStreamName(patronId);
        const result = await this.eventStore.readStream(streamName);

        if (result.notFound || result.events.length === 0) {
            return { success: false, error: `Patron not found: ${patronId}` };
        }

        const patron = Patron.fromEvents(result.events);
        const revision = await this.eventStore.getStreamRevision(streamName);

        return { success: true, patron, revision };
    }

    /**
     * Upgrade patron to researcher
     */
    async upgradePatronToResearcher(patronId) {
        const patronResult = await this.loadPatron(patronId);
        if (!patronResult.success) {
            return patronResult;
        }
        const { patron, revision } = patronResult;

        const upgradeResult = patron.upgradeToResearcher();
        if (!upgradeResult.success) {
            return upgradeResult;
        }

        const streamName = Patron.getStreamName(patronId);
        const appendResult = await this.eventStore.appendToStream(
            streamName,
            [upgradeResult.event],
            BigInt(revision)
        );

        if (!appendResult.success) {
            return appendResult;
        }

        return {
            success: true,
            message: `Patron "${patron.name}" upgraded to Researcher`,
        };
    }
}
