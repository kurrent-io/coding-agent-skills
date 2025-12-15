/**
 * Patron Aggregate
 *
 * Models library patrons with their holds and checkouts:
 * - Regular patrons: Max 5 simultaneous holds
 * - Researcher patrons: Unlimited holds, access to restricted books, open-ended holds
 *
 * Business Rules:
 * - Regular patrons limited to 5 holds
 * - Patrons with >2 overdue checkouts at a branch cannot place holds there
 * - Only researchers can hold restricted books
 * - Only researchers can request open-ended holds
 */

import {
    PatronType,
    HoldType,
    PatronEvents,
    createPatronCreatedEvent,
    createPatronTypeUpgradedEvent,
    createOverdueCheckoutRegisteredEvent,
} from './events.js';

const MAX_HOLDS_FOR_REGULAR = 5;
const MAX_OVERDUE_FOR_HOLDS = 2;

export class Patron {
    constructor() {
        this.patronId = null;
        this.patronType = null;
        this.name = null;
        this.email = null;
        this.holds = new Map();              // bookId -> { libraryBranchId, holdType, holdTill }
        this.checkouts = new Map();          // bookId -> { libraryBranchId, checkedOutAt, dueDate }
        this.overduesByBranch = new Map();   // libraryBranchId -> count
        this.version = -1;
    }

    /**
     * Factory method to create a new patron
     */
    static create(patronId, patronType, name, email) {
        const patron = new Patron();
        const event = createPatronCreatedEvent(patronId, patronType, name, email);
        patron.apply(event);
        return { patron, event };
    }

    /**
     * Reconstitute patron from event stream
     */
    static fromEvents(events) {
        const patron = new Patron();
        for (const event of events) {
            patron.apply(event);
            patron.version++;
        }
        return patron;
    }

    /**
     * Check if patron can place a hold at the given branch
     */
    canPlaceHoldAt(libraryBranchId, bookType) {
        // Check overdue limit at branch
        const overduesAtBranch = this.overduesByBranch.get(libraryBranchId) || 0;
        if (overduesAtBranch > MAX_OVERDUE_FOR_HOLDS) {
            return {
                allowed: false,
                reason: `Too many overdue checkouts (${overduesAtBranch}) at this branch`
            };
        }

        // Check hold limit for regular patrons
        if (this.patronType === PatronType.REGULAR) {
            if (this.holds.size >= MAX_HOLDS_FOR_REGULAR) {
                return {
                    allowed: false,
                    reason: `Regular patrons limited to ${MAX_HOLDS_FOR_REGULAR} holds`
                };
            }
        }

        // Check restricted book access
        if (bookType === 'Restricted' && this.patronType !== PatronType.RESEARCHER) {
            return {
                allowed: false,
                reason: 'Only researchers can hold restricted books'
            };
        }

        return { allowed: true };
    }

    /**
     * Get allowed hold types for this patron
     */
    getAllowedHoldTypes() {
        if (this.patronType === PatronType.RESEARCHER) {
            return [HoldType.OPEN_ENDED, HoldType.CLOSED_ENDED];
        }
        return [HoldType.CLOSED_ENDED];
    }

    /**
     * Record that a hold was placed
     */
    recordHoldPlaced(bookId, libraryBranchId, holdType, holdTill) {
        this.holds.set(bookId, { libraryBranchId, holdType, holdTill });
    }

    /**
     * Record that a hold was canceled or expired
     */
    recordHoldRemoved(bookId) {
        this.holds.delete(bookId);
    }

    /**
     * Record a checkout
     */
    recordCheckout(bookId, libraryBranchId, dueDate) {
        this.checkouts.set(bookId, {
            libraryBranchId,
            checkedOutAt: new Date().toISOString(),
            dueDate
        });
        // Remove from holds since it's now checked out
        this.holds.delete(bookId);
    }

    /**
     * Record a return
     */
    recordReturn(bookId) {
        this.checkouts.delete(bookId);
    }

    /**
     * Register an overdue checkout
     */
    registerOverdue(bookId, libraryBranchId) {
        const current = this.overduesByBranch.get(libraryBranchId) || 0;
        this.overduesByBranch.set(libraryBranchId, current + 1);

        return createOverdueCheckoutRegisteredEvent(this.patronId, bookId, libraryBranchId);
    }

    /**
     * Upgrade patron type (e.g., Regular -> Researcher)
     */
    upgradeToResearcher() {
        if (this.patronType === PatronType.RESEARCHER) {
            return { success: false, error: 'Patron is already a researcher' };
        }

        const event = createPatronTypeUpgradedEvent(this.patronId, PatronType.RESEARCHER);
        this.apply(event);
        return { success: true, event };
    }

    /**
     * Apply event to update state
     */
    apply(event) {
        const eventType = event.type || event.eventType;
        const data = event.data || event;

        switch (eventType) {
            case PatronEvents.PATRON_CREATED:
                this.patronId = data.patronId;
                this.patronType = data.patronType;
                this.name = data.name;
                this.email = data.email;
                break;

            case PatronEvents.PATRON_TYPE_UPGRADED:
                this.patronType = data.newType;
                break;

            case PatronEvents.OVERDUE_CHECKOUT_REGISTERED: {
                const current = this.overduesByBranch.get(data.libraryBranchId) || 0;
                this.overduesByBranch.set(data.libraryBranchId, current + 1);
                break;
            }

            // These events are primarily handled by the Book aggregate
            // but we track them for patron's view
            case 'BookPlacedOnHold':
                if (data.patronId === this.patronId) {
                    this.holds.set(data.bookId, {
                        libraryBranchId: data.libraryBranchId,
                        holdType: data.holdType,
                        holdTill: data.holdTill
                    });
                }
                break;

            case 'BookHoldCanceled':
            case 'BookHoldExpired':
                if (data.patronId === this.patronId) {
                    this.holds.delete(data.bookId);
                }
                break;

            case 'BookCheckedOut':
                if (data.patronId === this.patronId) {
                    this.holds.delete(data.bookId);
                    this.checkouts.set(data.bookId, {
                        libraryBranchId: data.libraryBranchId,
                        checkedOutAt: data.checkedOutAt,
                        dueDate: data.dueDate
                    });
                }
                break;

            case 'BookReturned':
                if (data.patronId === this.patronId) {
                    this.checkouts.delete(data.bookId);
                }
                break;
        }
    }

    /**
     * Get stream name for this patron
     */
    static getStreamName(patronId) {
        return `patron-${patronId}`;
    }

    /**
     * Get summary of patron's current state
     */
    getSummary() {
        return {
            patronId: this.patronId,
            patronType: this.patronType,
            name: this.name,
            email: this.email,
            holdsCount: this.holds.size,
            checkoutsCount: this.checkouts.size,
            holds: Array.from(this.holds.entries()),
            checkouts: Array.from(this.checkouts.entries()),
        };
    }
}
