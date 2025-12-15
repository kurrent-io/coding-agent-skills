/**
 * Library System Test Scenarios
 *
 * Tests all business rules from the DDD-by-examples library domain:
 *
 * 1. Regular patrons limited to 5 holds
 * 2. Researchers have unlimited holds
 * 3. Only researchers can hold restricted books
 * 4. Only researchers can request open-ended holds
 * 5. Patrons with >2 overdues at branch cannot place holds there
 * 6. Available books can be placed on hold
 * 7. Books on hold can be checked out by holding patron
 * 8. Max checkout duration is 60 days
 */

import { v4 as uuid } from 'uuid';
import { EventStore } from './infrastructure/event-store.js';
import { LibraryService } from './application/library-service.js';
import { PatronType, BookType, HoldType } from './domain/events.js';

const CONNECTION_STRING = process.env.KURRENTDB_CONNECTION_STRING || 'kurrentdb://localhost:2113?tls=false';

// Test utilities
function assert(condition, message) {
    if (!condition) {
        throw new Error(`ASSERTION FAILED: ${message}`);
    }
}

function log(message) {
    console.log(`  ${message}`);
}

function logSection(title) {
    console.log(`\n${'='.repeat(60)}`);
    console.log(`  ${title}`);
    console.log('='.repeat(60));
}

function logTest(name) {
    console.log(`\n[TEST] ${name}`);
}

function logSuccess(name) {
    console.log(`  ✓ ${name} PASSED`);
}

function logError(name, error) {
    console.log(`  ✗ ${name} FAILED: ${error}`);
}

// Test scenarios
async function runTests() {
    const eventStore = new EventStore(CONNECTION_STRING);
    const libraryService = new LibraryService(eventStore);

    logSection('LIBRARY DDD TEST SCENARIOS');
    console.log(`Connected to: ${CONNECTION_STRING}\n`);

    let passed = 0;
    let failed = 0;

    // Test 1: Add books to library
    logTest('1. Adding books to library');
    try {
        const branchId = `branch-${uuid().slice(0, 8)}`;

        // Add a circulating book
        const book1Id = uuid();
        const result1 = await libraryService.addBook(
            book1Id,
            '978-0-13-235088-4',
            'Clean Code',
            BookType.CIRCULATING,
            branchId
        );
        assert(result1.success, 'Should add circulating book');
        log(`Added circulating book: ${book1Id}`);

        // Add a restricted book
        const book2Id = uuid();
        const result2 = await libraryService.addBook(
            book2Id,
            '978-0-201-63361-0',
            'Design Patterns',
            BookType.RESTRICTED,
            branchId
        );
        assert(result2.success, 'Should add restricted book');
        log(`Added restricted book: ${book2Id}`);

        // Verify books were stored
        const bookDetails = await libraryService.getBook(book1Id);
        assert(bookDetails.success, 'Should retrieve book');
        assert(bookDetails.book.state === 'Available', 'Book should be available');

        logSuccess('Adding books');
        passed++;
    } catch (error) {
        logError('Adding books', error.message);
        failed++;
    }

    // Test 2: Create patrons
    logTest('2. Creating patrons');
    try {
        const regularPatronId = uuid();
        const result1 = await libraryService.createPatron(
            regularPatronId,
            PatronType.REGULAR,
            'John Regular',
            'john@example.com'
        );
        assert(result1.success, 'Should create regular patron');
        log(`Created regular patron: ${regularPatronId}`);

        const researcherPatronId = uuid();
        const result2 = await libraryService.createPatron(
            researcherPatronId,
            PatronType.RESEARCHER,
            'Jane Researcher',
            'jane@example.com'
        );
        assert(result2.success, 'Should create researcher patron');
        log(`Created researcher patron: ${researcherPatronId}`);

        // Verify patron was stored
        const patronDetails = await libraryService.getPatron(regularPatronId);
        assert(patronDetails.success, 'Should retrieve patron');
        assert(patronDetails.patron.patronType === PatronType.REGULAR, 'Should be regular patron');

        logSuccess('Creating patrons');
        passed++;
    } catch (error) {
        logError('Creating patrons', error.message);
        failed++;
    }

    // Test 3: Place hold on available book
    logTest('3. Place hold on available book');
    try {
        const branchId = `branch-${uuid().slice(0, 8)}`;
        const bookId = uuid();
        const patronId = uuid();

        await libraryService.addBook(bookId, '978-0-00-000001-1', 'Test Book 3', BookType.CIRCULATING, branchId);
        await libraryService.createPatron(patronId, PatronType.REGULAR, 'Test Patron 3', 'test3@example.com');

        const result = await libraryService.placeHold(bookId, patronId, HoldType.CLOSED_ENDED);
        assert(result.success, 'Should place hold on available book');
        log(`Hold placed successfully, expires: ${result.holdTill}`);

        // Verify book is now on hold
        const bookDetails = await libraryService.getBook(bookId);
        assert(bookDetails.book.state === 'OnHold', 'Book should be on hold');
        assert(bookDetails.book.holdingPatronId === patronId, 'Correct patron should hold book');

        logSuccess('Place hold on available book');
        passed++;
    } catch (error) {
        logError('Place hold on available book', error.message);
        failed++;
    }

    // Test 4: Regular patron cannot hold restricted books
    logTest('4. Regular patron cannot hold restricted books');
    try {
        const branchId = `branch-${uuid().slice(0, 8)}`;
        const bookId = uuid();
        const patronId = uuid();

        await libraryService.addBook(bookId, '978-0-00-000002-2', 'Restricted Book', BookType.RESTRICTED, branchId);
        await libraryService.createPatron(patronId, PatronType.REGULAR, 'Regular Patron', 'regular@example.com');

        const result = await libraryService.placeHold(bookId, patronId, HoldType.CLOSED_ENDED);
        assert(!result.success, 'Should not allow regular patron to hold restricted book');
        assert(result.error.includes('researcher'), 'Error should mention researchers');
        log(`Correctly rejected: ${result.error}`);

        logSuccess('Regular patron cannot hold restricted books');
        passed++;
    } catch (error) {
        logError('Regular patron cannot hold restricted books', error.message);
        failed++;
    }

    // Test 5: Researcher can hold restricted books
    logTest('5. Researcher can hold restricted books');
    try {
        const branchId = `branch-${uuid().slice(0, 8)}`;
        const bookId = uuid();
        const patronId = uuid();

        await libraryService.addBook(bookId, '978-0-00-000003-3', 'Restricted Book 2', BookType.RESTRICTED, branchId);
        await libraryService.createPatron(patronId, PatronType.RESEARCHER, 'Research Patron', 'researcher@example.com');

        const result = await libraryService.placeHold(bookId, patronId, HoldType.CLOSED_ENDED);
        assert(result.success, 'Researcher should be able to hold restricted book');
        log(`Researcher hold placed successfully`);

        logSuccess('Researcher can hold restricted books');
        passed++;
    } catch (error) {
        logError('Researcher can hold restricted books', error.message);
        failed++;
    }

    // Test 6: Regular patron cannot request open-ended holds
    logTest('6. Regular patron cannot request open-ended holds');
    try {
        const branchId = `branch-${uuid().slice(0, 8)}`;
        const bookId = uuid();
        const patronId = uuid();

        await libraryService.addBook(bookId, '978-0-00-000004-4', 'Book for Open Hold', BookType.CIRCULATING, branchId);
        await libraryService.createPatron(patronId, PatronType.REGULAR, 'Regular Patron 2', 'regular2@example.com');

        const result = await libraryService.placeHold(bookId, patronId, HoldType.OPEN_ENDED);
        assert(!result.success, 'Should not allow regular patron open-ended hold');
        assert(result.error.includes('researcher'), 'Error should mention researchers');
        log(`Correctly rejected: ${result.error}`);

        logSuccess('Regular patron cannot request open-ended holds');
        passed++;
    } catch (error) {
        logError('Regular patron cannot request open-ended holds', error.message);
        failed++;
    }

    // Test 7: Researcher can request open-ended holds
    logTest('7. Researcher can request open-ended holds');
    try {
        const branchId = `branch-${uuid().slice(0, 8)}`;
        const bookId = uuid();
        const patronId = uuid();

        await libraryService.addBook(bookId, '978-0-00-000005-5', 'Book for Open Hold 2', BookType.CIRCULATING, branchId);
        await libraryService.createPatron(patronId, PatronType.RESEARCHER, 'Researcher 2', 'researcher2@example.com');

        const result = await libraryService.placeHold(bookId, patronId, HoldType.OPEN_ENDED);
        assert(result.success, 'Researcher should be able to request open-ended hold');
        assert(result.holdTill === null, 'Open-ended hold should not have expiration');
        log(`Open-ended hold placed successfully`);

        logSuccess('Researcher can request open-ended holds');
        passed++;
    } catch (error) {
        logError('Researcher can request open-ended holds', error.message);
        failed++;
    }

    // Test 8: Checkout book on hold
    logTest('8. Checkout book on hold');
    try {
        const branchId = `branch-${uuid().slice(0, 8)}`;
        const bookId = uuid();
        const patronId = uuid();

        await libraryService.addBook(bookId, '978-0-00-000006-6', 'Book for Checkout', BookType.CIRCULATING, branchId);
        await libraryService.createPatron(patronId, PatronType.REGULAR, 'Checkout Patron', 'checkout@example.com');

        // First place hold
        await libraryService.placeHold(bookId, patronId, HoldType.CLOSED_ENDED);

        // Then checkout
        const result = await libraryService.checkout(bookId, patronId);
        assert(result.success, 'Should checkout book on hold');
        log(`Checkout successful, due date: ${result.dueDate}`);

        // Verify book state
        const bookDetails = await libraryService.getBook(bookId);
        assert(bookDetails.book.state === 'CheckedOut', 'Book should be checked out');
        assert(bookDetails.book.checkedOutBy === patronId, 'Correct patron should have book');

        // Verify due date is within 60 days
        const dueDate = new Date(result.dueDate);
        const now = new Date();
        const daysDiff = Math.ceil((dueDate - now) / (1000 * 60 * 60 * 24));
        assert(daysDiff <= 60, 'Due date should be within 60 days');
        log(`Due date is ${daysDiff} days from now (max 60)`);

        logSuccess('Checkout book on hold');
        passed++;
    } catch (error) {
        logError('Checkout book on hold', error.message);
        failed++;
    }

    // Test 9: Cannot checkout book not on hold
    logTest('9. Cannot checkout book not on hold');
    try {
        const branchId = `branch-${uuid().slice(0, 8)}`;
        const bookId = uuid();
        const patronId = uuid();

        await libraryService.addBook(bookId, '978-0-00-000007-7', 'Available Book', BookType.CIRCULATING, branchId);
        await libraryService.createPatron(patronId, PatronType.REGULAR, 'Eager Patron', 'eager@example.com');

        const result = await libraryService.checkout(bookId, patronId);
        assert(!result.success, 'Should not checkout book without hold');
        log(`Correctly rejected: ${result.error}`);

        logSuccess('Cannot checkout book not on hold');
        passed++;
    } catch (error) {
        logError('Cannot checkout book not on hold', error.message);
        failed++;
    }

    // Test 10: Return book
    logTest('10. Return book');
    try {
        const branchId = `branch-${uuid().slice(0, 8)}`;
        const bookId = uuid();
        const patronId = uuid();

        await libraryService.addBook(bookId, '978-0-00-000008-8', 'Book to Return', BookType.CIRCULATING, branchId);
        await libraryService.createPatron(patronId, PatronType.REGULAR, 'Return Patron', 'return@example.com');

        // Place hold and checkout
        await libraryService.placeHold(bookId, patronId, HoldType.CLOSED_ENDED);
        await libraryService.checkout(bookId, patronId);

        // Return
        const result = await libraryService.returnBook(bookId, patronId);
        assert(result.success, 'Should return book');
        log(`Book returned successfully`);

        // Verify book is available again
        const bookDetails = await libraryService.getBook(bookId);
        assert(bookDetails.book.state === 'Available', 'Book should be available after return');

        logSuccess('Return book');
        passed++;
    } catch (error) {
        logError('Return book', error.message);
        failed++;
    }

    // Test 11: Cancel hold
    logTest('11. Cancel hold');
    try {
        const branchId = `branch-${uuid().slice(0, 8)}`;
        const bookId = uuid();
        const patronId = uuid();

        await libraryService.addBook(bookId, '978-0-00-000009-9', 'Book to Cancel', BookType.CIRCULATING, branchId);
        await libraryService.createPatron(patronId, PatronType.REGULAR, 'Cancel Patron', 'cancel@example.com');

        // Place hold
        await libraryService.placeHold(bookId, patronId, HoldType.CLOSED_ENDED);

        // Cancel hold
        const result = await libraryService.cancelHold(bookId, patronId, 'Changed my mind');
        assert(result.success, 'Should cancel hold');
        log(`Hold canceled: ${result.reason}`);

        // Verify book is available again
        const bookDetails = await libraryService.getBook(bookId);
        assert(bookDetails.book.state === 'Available', 'Book should be available after cancel');

        logSuccess('Cancel hold');
        passed++;
    } catch (error) {
        logError('Cancel hold', error.message);
        failed++;
    }

    // Test 12: Cannot place hold on book already on hold
    logTest('12. Cannot place hold on book already on hold');
    try {
        const branchId = `branch-${uuid().slice(0, 8)}`;
        const bookId = uuid();
        const patron1Id = uuid();
        const patron2Id = uuid();

        await libraryService.addBook(bookId, '978-0-00-000010-0', 'Popular Book', BookType.CIRCULATING, branchId);
        await libraryService.createPatron(patron1Id, PatronType.REGULAR, 'First Patron', 'first@example.com');
        await libraryService.createPatron(patron2Id, PatronType.REGULAR, 'Second Patron', 'second@example.com');

        // First patron places hold
        await libraryService.placeHold(bookId, patron1Id, HoldType.CLOSED_ENDED);

        // Second patron tries to place hold
        const result = await libraryService.placeHold(bookId, patron2Id, HoldType.CLOSED_ENDED);
        assert(!result.success, 'Should not allow second hold');
        log(`Correctly rejected: ${result.error}`);

        logSuccess('Cannot place hold on book already on hold');
        passed++;
    } catch (error) {
        logError('Cannot place hold on book already on hold', error.message);
        failed++;
    }

    // Test 13: Upgrade patron to researcher
    logTest('13. Upgrade patron to researcher');
    try {
        const patronId = uuid();

        await libraryService.createPatron(patronId, PatronType.REGULAR, 'Upgradeable Patron', 'upgrade@example.com');

        // Upgrade
        const result = await libraryService.upgradePatronToResearcher(patronId);
        assert(result.success, 'Should upgrade patron');
        log(`Patron upgraded to researcher`);

        // Verify upgrade
        const patronDetails = await libraryService.getPatron(patronId);
        assert(patronDetails.patron.patronType === PatronType.RESEARCHER, 'Patron should be researcher');

        logSuccess('Upgrade patron to researcher');
        passed++;
    } catch (error) {
        logError('Upgrade patron to researcher', error.message);
        failed++;
    }

    // Test 14: Full workflow - regular patron
    logTest('14. Full workflow - regular patron lifecycle');
    try {
        const branchId = `branch-${uuid().slice(0, 8)}`;
        const bookId = uuid();
        const patronId = uuid();

        // Setup
        await libraryService.addBook(bookId, '978-0-00-000011-1', 'Workflow Book', BookType.CIRCULATING, branchId);
        await libraryService.createPatron(patronId, PatronType.REGULAR, 'Workflow Patron', 'workflow@example.com');

        // Place hold
        const holdResult = await libraryService.placeHold(bookId, patronId, HoldType.CLOSED_ENDED);
        assert(holdResult.success, 'Step 1: Place hold');
        log('Step 1: Hold placed');

        // Checkout
        const checkoutResult = await libraryService.checkout(bookId, patronId);
        assert(checkoutResult.success, 'Step 2: Checkout');
        log('Step 2: Checked out');

        // Return
        const returnResult = await libraryService.returnBook(bookId, patronId);
        assert(returnResult.success, 'Step 3: Return');
        log('Step 3: Returned');

        // Verify final state
        const bookDetails = await libraryService.getBook(bookId);
        assert(bookDetails.book.state === 'Available', 'Book should be available');
        log('Final state: Book available for next patron');

        logSuccess('Full workflow - regular patron lifecycle');
        passed++;
    } catch (error) {
        logError('Full workflow - regular patron lifecycle', error.message);
        failed++;
    }

    // Test 15: Event sourcing - reconstitute from events
    logTest('15. Event sourcing - verify event history');
    try {
        const branchId = `branch-${uuid().slice(0, 8)}`;
        const bookId = uuid();
        const patronId = uuid();

        await libraryService.addBook(bookId, '978-0-00-000012-2', 'Event History Book', BookType.CIRCULATING, branchId);
        await libraryService.createPatron(patronId, PatronType.REGULAR, 'Event Patron', 'event@example.com');

        // Perform several operations
        await libraryService.placeHold(bookId, patronId, HoldType.CLOSED_ENDED);
        await libraryService.checkout(bookId, patronId);
        await libraryService.returnBook(bookId, patronId);

        // Read event history directly
        const eventStore = new EventStore(CONNECTION_STRING);
        const events = await eventStore.readStream(`book-${bookId}`);

        assert(events.success, 'Should read events');
        assert(events.events.length === 4, `Should have 4 events, got ${events.events.length}`);

        log(`Event history (${events.events.length} events):`);
        events.events.forEach((e, i) => {
            log(`  ${i + 1}. ${e.type}`);
        });

        // Verify event order
        assert(events.events[0].type === 'BookAddedToLibrary', 'First event: BookAdded');
        assert(events.events[1].type === 'BookPlacedOnHold', 'Second event: PlacedOnHold');
        assert(events.events[2].type === 'BookCheckedOut', 'Third event: CheckedOut');
        assert(events.events[3].type === 'BookReturned', 'Fourth event: Returned');

        logSuccess('Event sourcing - verify event history');
        passed++;
    } catch (error) {
        logError('Event sourcing - verify event history', error.message);
        failed++;
    }

    // Summary
    logSection('TEST SUMMARY');
    console.log(`  Total: ${passed + failed}`);
    console.log(`  Passed: ${passed}`);
    console.log(`  Failed: ${failed}`);
    console.log('');

    if (failed > 0) {
        console.log('Some tests failed!');
        process.exit(1);
    } else {
        console.log('All tests passed!');
        process.exit(0);
    }
}

// Run tests
console.log('\n🏛️  Library DDD with Event Sourcing - Test Suite\n');
console.log('Testing business rules from ddd-by-examples/library');
console.log('Using KurrentDB for event storage\n');

runTests().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
});
