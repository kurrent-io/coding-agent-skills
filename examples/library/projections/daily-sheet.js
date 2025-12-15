/**
 * Daily Sheet Projections
 *
 * Read models for:
 * - Expiring holds sheet: Lists holds that expire today
 * - Overdue checkouts sheet: Lists overdue checkouts
 *
 * These projections demonstrate CQRS pattern with KurrentDB
 */

import { streamNameFilter, eventTypeFilter, START } from '@kurrent/kurrentdb-client';
import { BookEvents, PatronEvents } from '../domain/events.js';

export class DailySheetProjection {
    constructor(eventStore) {
        this.eventStore = eventStore;

        // In-memory read models (in production, use a separate read store)
        this.expiringHolds = new Map();     // date -> [{ bookId, patronId, libraryBranchId, holdTill }]
        this.overdueCheckouts = new Map();  // patronId -> [{ bookId, libraryBranchId, dueDate }]
        this.activeHolds = new Map();       // bookId -> { patronId, libraryBranchId, holdTill }
        this.activeCheckouts = new Map();   // bookId -> { patronId, libraryBranchId, dueDate }
    }

    /**
     * Start projection by subscribing to relevant events
     */
    async start() {
        console.log('Starting Daily Sheet Projection...');

        // Subscribe to book events
        const subscription = this.eventStore.subscribeToAll({
            fromPosition: START,
            filter: streamNameFilter({ prefixes: ['book-'] }),
        });

        // Process events
        for await (const resolvedEvent of subscription) {
            if (resolvedEvent.event) {
                this.processEvent(resolvedEvent.event);
            }
        }
    }

    /**
     * Process a single event
     */
    processEvent(event) {
        const { type, data } = event;

        switch (type) {
            case BookEvents.BOOK_PLACED_ON_HOLD:
                this.handleHoldPlaced(data);
                break;

            case BookEvents.BOOK_HOLD_CANCELED:
            case BookEvents.BOOK_HOLD_EXPIRED:
                this.handleHoldRemoved(data);
                break;

            case BookEvents.BOOK_CHECKED_OUT:
                this.handleCheckout(data);
                break;

            case BookEvents.BOOK_RETURNED:
                this.handleReturn(data);
                break;
        }
    }

    handleHoldPlaced(data) {
        const { bookId, patronId, libraryBranchId, holdTill } = data;

        // Track active hold
        this.activeHolds.set(bookId, { patronId, libraryBranchId, holdTill });

        // If closed-ended hold, add to expiring holds
        if (holdTill) {
            const expiryDate = holdTill.split('T')[0]; // Get date part
            if (!this.expiringHolds.has(expiryDate)) {
                this.expiringHolds.set(expiryDate, []);
            }
            this.expiringHolds.get(expiryDate).push({
                bookId,
                patronId,
                libraryBranchId,
                holdTill,
            });
        }
    }

    handleHoldRemoved(data) {
        const { bookId } = data;
        this.activeHolds.delete(bookId);
    }

    handleCheckout(data) {
        const { bookId, patronId, libraryBranchId, dueDate } = data;

        // Remove from active holds
        this.activeHolds.delete(bookId);

        // Track active checkout
        this.activeCheckouts.set(bookId, { patronId, libraryBranchId, dueDate });
    }

    handleReturn(data) {
        const { bookId, patronId } = data;

        // Remove from active checkouts
        this.activeCheckouts.delete(bookId);

        // Remove from overdue list if present
        if (this.overdueCheckouts.has(patronId)) {
            const overdues = this.overdueCheckouts.get(patronId);
            const filtered = overdues.filter(o => o.bookId !== bookId);
            if (filtered.length > 0) {
                this.overdueCheckouts.set(patronId, filtered);
            } else {
                this.overdueCheckouts.delete(patronId);
            }
        }
    }

    /**
     * Get holds expiring on a specific date
     */
    getExpiringHoldsForDate(date) {
        const dateStr = typeof date === 'string' ? date : date.toISOString().split('T')[0];
        return this.expiringHolds.get(dateStr) || [];
    }

    /**
     * Get holds expiring today
     */
    getExpiringHoldsToday() {
        const today = new Date().toISOString().split('T')[0];
        return this.getExpiringHoldsForDate(today);
    }

    /**
     * Check and update overdue checkouts
     */
    updateOverdueCheckouts() {
        const now = new Date();

        for (const [bookId, checkout] of this.activeCheckouts.entries()) {
            const dueDate = new Date(checkout.dueDate);
            if (now > dueDate) {
                // Add to overdue list
                if (!this.overdueCheckouts.has(checkout.patronId)) {
                    this.overdueCheckouts.set(checkout.patronId, []);
                }

                const existingOverdues = this.overdueCheckouts.get(checkout.patronId);
                if (!existingOverdues.some(o => o.bookId === bookId)) {
                    existingOverdues.push({
                        bookId,
                        libraryBranchId: checkout.libraryBranchId,
                        dueDate: checkout.dueDate,
                    });
                }
            }
        }
    }

    /**
     * Get all overdue checkouts
     */
    getOverdueCheckouts() {
        this.updateOverdueCheckouts();
        return Array.from(this.overdueCheckouts.entries()).map(([patronId, overdues]) => ({
            patronId,
            overdues,
        }));
    }

    /**
     * Get overdue count for a patron at a specific branch
     */
    getOverdueCountForPatronAtBranch(patronId, libraryBranchId) {
        this.updateOverdueCheckouts();
        const overdues = this.overdueCheckouts.get(patronId) || [];
        return overdues.filter(o => o.libraryBranchId === libraryBranchId).length;
    }

    /**
     * Get current statistics
     */
    getStatistics() {
        return {
            activeHoldsCount: this.activeHolds.size,
            activeCheckoutsCount: this.activeCheckouts.size,
            expiringTodayCount: this.getExpiringHoldsToday().length,
            overduePatronsCount: this.overdueCheckouts.size,
        };
    }
}

/**
 * Catalog Projection
 *
 * Maintains a searchable catalog of all books
 */
export class CatalogProjection {
    constructor(eventStore) {
        this.eventStore = eventStore;
        this.books = new Map();  // bookId -> book details
    }

    /**
     * Start projection
     */
    async start() {
        console.log('Starting Catalog Projection...');

        const subscription = this.eventStore.subscribeToAll({
            fromPosition: START,
            filter: streamNameFilter({ prefixes: ['book-'] }),
        });

        for await (const resolvedEvent of subscription) {
            if (resolvedEvent.event) {
                this.processEvent(resolvedEvent.event);
            }
        }
    }

    processEvent(event) {
        const { type, data } = event;

        switch (type) {
            case 'BookAddedToLibrary':
                this.books.set(data.bookId, {
                    bookId: data.bookId,
                    isbn: data.isbn,
                    title: data.title,
                    bookType: data.bookType,
                    libraryBranchId: data.libraryBranchId,
                    state: 'Available',
                    addedAt: data.occurredAt,
                });
                break;

            case 'BookPlacedOnHold':
                if (this.books.has(data.bookId)) {
                    const book = this.books.get(data.bookId);
                    book.state = 'OnHold';
                    book.holdingPatronId = data.patronId;
                }
                break;

            case 'BookHoldCanceled':
            case 'BookHoldExpired':
                if (this.books.has(data.bookId)) {
                    const book = this.books.get(data.bookId);
                    book.state = 'Available';
                    book.holdingPatronId = null;
                }
                break;

            case 'BookCheckedOut':
                if (this.books.has(data.bookId)) {
                    const book = this.books.get(data.bookId);
                    book.state = 'CheckedOut';
                    book.checkedOutBy = data.patronId;
                    book.dueDate = data.dueDate;
                    book.holdingPatronId = null;
                }
                break;

            case 'BookReturned':
                if (this.books.has(data.bookId)) {
                    const book = this.books.get(data.bookId);
                    book.state = 'Available';
                    book.checkedOutBy = null;
                    book.dueDate = null;
                }
                break;
        }
    }

    /**
     * Get all available books
     */
    getAvailableBooks() {
        return Array.from(this.books.values()).filter(b => b.state === 'Available');
    }

    /**
     * Get books by library branch
     */
    getBooksByBranch(libraryBranchId) {
        return Array.from(this.books.values()).filter(b => b.libraryBranchId === libraryBranchId);
    }

    /**
     * Search books by title
     */
    searchByTitle(query) {
        const lowerQuery = query.toLowerCase();
        return Array.from(this.books.values()).filter(b =>
            b.title.toLowerCase().includes(lowerQuery)
        );
    }

    /**
     * Get catalog statistics
     */
    getStatistics() {
        const books = Array.from(this.books.values());
        return {
            totalBooks: books.length,
            available: books.filter(b => b.state === 'Available').length,
            onHold: books.filter(b => b.state === 'OnHold').length,
            checkedOut: books.filter(b => b.state === 'CheckedOut').length,
        };
    }
}
