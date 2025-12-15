/**
 * Book Aggregate
 *
 * Models the book lifecycle in the library:
 * - Available: Can be placed on hold
 * - OnHold: Reserved by a patron
 * - CheckedOut: Borrowed by a patron
 *
 * Business Rules:
 * - Only available books can be placed on hold
 * - Only books on hold can be checked out (by the patron holding them)
 * - Restricted books can only be held by researchers
 */

import {
    BookState,
    BookType,
    BookEvents,
    createBookAddedEvent,
    createBookPlacedOnHoldEvent,
    createBookHoldCanceledEvent,
    createBookCheckedOutEvent,
    createBookReturnedEvent,
} from './events.js';

export class Book {
    constructor() {
        this.bookId = null;
        this.isbn = null;
        this.title = null;
        this.bookType = null;
        this.libraryBranchId = null;
        this.state = null;
        this.holdingPatronId = null;
        this.holdTill = null;
        this.checkedOutBy = null;
        this.dueDate = null;
        this.version = -1;
    }

    /**
     * Factory method to create a new book (stream doesn't exist)
     */
    static create(bookId, isbn, title, bookType, libraryBranchId) {
        const book = new Book();
        const event = createBookAddedEvent(bookId, isbn, title, bookType, libraryBranchId);
        book.apply(event);
        return { book, event };
    }

    /**
     * Reconstitute book from event stream
     */
    static fromEvents(events) {
        const book = new Book();
        for (const event of events) {
            book.apply(event);
            book.version++;
        }
        return book;
    }

    /**
     * Place hold on book
     * @param {string} patronId
     * @param {string} patronType - 'Regular' or 'Researcher'
     * @param {string} holdType - 'OpenEnded' or 'ClosedEnded'
     * @param {Date|null} holdTill - expiration for closed-ended holds
     */
    placeOnHold(patronId, patronType, holdType, holdTill = null) {
        // Business rule: Only available books can be placed on hold
        if (this.state !== BookState.AVAILABLE) {
            return { success: false, error: `Cannot place hold on book in state: ${this.state}` };
        }

        // Business rule: Restricted books can only be held by researchers
        if (this.bookType === BookType.RESTRICTED && patronType !== 'Researcher') {
            return { success: false, error: 'Only researchers can hold restricted books' };
        }

        // Business rule: Open-ended holds only for researchers
        if (holdType === 'OpenEnded' && patronType !== 'Researcher') {
            return { success: false, error: 'Only researchers can request open-ended holds' };
        }

        const event = createBookPlacedOnHoldEvent(
            this.bookId,
            patronId,
            this.libraryBranchId,
            holdType,
            holdTill
        );
        this.apply(event);
        return { success: true, event };
    }

    /**
     * Cancel hold on book
     */
    cancelHold(patronId, reason = 'Canceled by patron') {
        if (this.state !== BookState.ON_HOLD) {
            return { success: false, error: 'Book is not on hold' };
        }

        if (this.holdingPatronId !== patronId) {
            return { success: false, error: 'Only the holding patron can cancel the hold' };
        }

        const event = createBookHoldCanceledEvent(
            this.bookId,
            patronId,
            this.libraryBranchId,
            reason
        );
        this.apply(event);
        return { success: true, event };
    }

    /**
     * Checkout book (must be on hold by the same patron)
     */
    checkout(patronId) {
        if (this.state !== BookState.ON_HOLD) {
            return { success: false, error: 'Book must be on hold to checkout' };
        }

        if (this.holdingPatronId !== patronId) {
            return { success: false, error: 'Book is on hold by another patron' };
        }

        // Business rule: Max checkout duration is 60 days
        const dueDate = new Date();
        dueDate.setDate(dueDate.getDate() + 60);

        const event = createBookCheckedOutEvent(
            this.bookId,
            patronId,
            this.libraryBranchId,
            dueDate.toISOString()
        );
        this.apply(event);
        return { success: true, event };
    }

    /**
     * Return book
     */
    returnBook(patronId) {
        if (this.state !== BookState.CHECKED_OUT) {
            return { success: false, error: 'Book is not checked out' };
        }

        if (this.checkedOutBy !== patronId) {
            return { success: false, error: 'Book was checked out by another patron' };
        }

        const event = createBookReturnedEvent(
            this.bookId,
            patronId,
            this.libraryBranchId
        );
        this.apply(event);
        return { success: true, event };
    }

    /**
     * Check if hold has expired
     */
    isHoldExpired() {
        if (this.state !== BookState.ON_HOLD || !this.holdTill) {
            return false;
        }
        return new Date() > new Date(this.holdTill);
    }

    /**
     * Apply event to update state
     */
    apply(event) {
        const eventType = event.type || event.eventType;
        const data = event.data || event;

        switch (eventType) {
            case BookEvents.BOOK_ADDED:
                this.bookId = data.bookId;
                this.isbn = data.isbn;
                this.title = data.title;
                this.bookType = data.bookType;
                this.libraryBranchId = data.libraryBranchId;
                this.state = BookState.AVAILABLE;
                break;

            case BookEvents.BOOK_PLACED_ON_HOLD:
                this.state = BookState.ON_HOLD;
                this.holdingPatronId = data.patronId;
                this.holdTill = data.holdTill;
                break;

            case BookEvents.BOOK_HOLD_CANCELED:
            case BookEvents.BOOK_HOLD_EXPIRED:
                this.state = BookState.AVAILABLE;
                this.holdingPatronId = null;
                this.holdTill = null;
                break;

            case BookEvents.BOOK_CHECKED_OUT:
                this.state = BookState.CHECKED_OUT;
                this.checkedOutBy = data.patronId;
                this.dueDate = data.dueDate;
                this.holdingPatronId = null;
                this.holdTill = null;
                break;

            case BookEvents.BOOK_RETURNED:
                this.state = BookState.AVAILABLE;
                this.checkedOutBy = null;
                this.dueDate = null;
                break;
        }
    }

    /**
     * Get stream name for this book
     */
    static getStreamName(bookId) {
        return `book-${bookId}`;
    }
}
