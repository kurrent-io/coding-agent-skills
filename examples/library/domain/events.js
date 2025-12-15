/**
 * Domain Events for Library System
 *
 * Based on DDD-by-examples library domain:
 * - Book lifecycle events
 * - Patron events
 * - Hold events
 * - Checkout events
 */

// Book Events
export const BookEvents = {
    BOOK_ADDED: 'BookAddedToLibrary',
    BOOK_PLACED_ON_HOLD: 'BookPlacedOnHold',
    BOOK_HOLD_CANCELED: 'BookHoldCanceled',
    BOOK_HOLD_EXPIRED: 'BookHoldExpired',
    BOOK_CHECKED_OUT: 'BookCheckedOut',
    BOOK_RETURNED: 'BookReturned',
};

// Patron Events
export const PatronEvents = {
    PATRON_CREATED: 'PatronCreated',
    PATRON_TYPE_UPGRADED: 'PatronTypeUpgraded',
    PATRON_HOLD_PLACED: 'PatronHoldPlaced',
    PATRON_HOLD_CANCELED: 'PatronHoldCanceled',
    PATRON_CHECKOUT_RECORDED: 'PatronCheckoutRecorded',
    PATRON_RETURN_RECORDED: 'PatronReturnRecorded',
    OVERDUE_CHECKOUT_REGISTERED: 'OverdueCheckoutRegistered',
};

// Book Types
export const BookType = {
    CIRCULATING: 'Circulating',
    RESTRICTED: 'Restricted',
};

// Patron Types
export const PatronType = {
    REGULAR: 'Regular',
    RESEARCHER: 'Researcher',
};

// Hold Types
export const HoldType = {
    OPEN_ENDED: 'OpenEnded',      // Only for researchers
    CLOSED_ENDED: 'ClosedEnded',  // Expires after fixed duration
};

// Book States
export const BookState = {
    AVAILABLE: 'Available',
    ON_HOLD: 'OnHold',
    CHECKED_OUT: 'CheckedOut',
};

/**
 * Event factory functions
 */
export function createBookAddedEvent(bookId, isbn, title, bookType, libraryBranchId) {
    return {
        type: BookEvents.BOOK_ADDED,
        data: {
            bookId,
            isbn,
            title,
            bookType,
            libraryBranchId,
            occurredAt: new Date().toISOString(),
        }
    };
}

export function createBookPlacedOnHoldEvent(bookId, patronId, libraryBranchId, holdType, holdTill = null) {
    return {
        type: BookEvents.BOOK_PLACED_ON_HOLD,
        data: {
            bookId,
            patronId,
            libraryBranchId,
            holdType,
            holdTill,  // null for open-ended holds
            holdPlacedAt: new Date().toISOString(),
        }
    };
}

export function createBookHoldCanceledEvent(bookId, patronId, libraryBranchId, reason) {
    return {
        type: BookEvents.BOOK_HOLD_CANCELED,
        data: {
            bookId,
            patronId,
            libraryBranchId,
            reason,
            canceledAt: new Date().toISOString(),
        }
    };
}

export function createBookHoldExpiredEvent(bookId, patronId, libraryBranchId) {
    return {
        type: BookEvents.BOOK_HOLD_EXPIRED,
        data: {
            bookId,
            patronId,
            libraryBranchId,
            expiredAt: new Date().toISOString(),
        }
    };
}

export function createBookCheckedOutEvent(bookId, patronId, libraryBranchId, dueDate) {
    return {
        type: BookEvents.BOOK_CHECKED_OUT,
        data: {
            bookId,
            patronId,
            libraryBranchId,
            checkedOutAt: new Date().toISOString(),
            dueDate,  // Max 60 days
        }
    };
}

export function createBookReturnedEvent(bookId, patronId, libraryBranchId) {
    return {
        type: BookEvents.BOOK_RETURNED,
        data: {
            bookId,
            patronId,
            libraryBranchId,
            returnedAt: new Date().toISOString(),
        }
    };
}

export function createPatronCreatedEvent(patronId, patronType, name, email) {
    return {
        type: PatronEvents.PATRON_CREATED,
        data: {
            patronId,
            patronType,
            name,
            email,
            createdAt: new Date().toISOString(),
        }
    };
}

export function createPatronTypeUpgradedEvent(patronId, newType) {
    return {
        type: PatronEvents.PATRON_TYPE_UPGRADED,
        data: {
            patronId,
            newType,
            upgradedAt: new Date().toISOString(),
        }
    };
}

export function createOverdueCheckoutRegisteredEvent(patronId, bookId, libraryBranchId) {
    return {
        type: PatronEvents.OVERDUE_CHECKOUT_REGISTERED,
        data: {
            patronId,
            bookId,
            libraryBranchId,
            registeredAt: new Date().toISOString(),
        }
    };
}
