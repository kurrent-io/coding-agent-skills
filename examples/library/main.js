/**
 * Library Application - Main Entry Point
 *
 * Demonstrates the library DDD system with event sourcing
 */

import { v4 as uuid } from 'uuid';
import { LibraryService } from './application/library-service.js';
import { PatronType, BookType, HoldType } from './domain/events.js';

const CONNECTION_STRING = process.env.KURRENTDB_CONNECTION_STRING || 'kurrentdb://localhost:2113?tls=false';

async function main() {
    console.log('📚 Library DDD Application with Event Sourcing\n');
    console.log(`Connected to KurrentDB: ${CONNECTION_STRING}\n`);

    const libraryService = new LibraryService();

    // Create a library branch
    const branchId = 'main-branch';

    // Add some books
    console.log('Adding books to the library...\n');

    const books = [
        { id: uuid(), isbn: '978-0-13-235088-4', title: 'Clean Code', type: BookType.CIRCULATING },
        { id: uuid(), isbn: '978-0-201-63361-0', title: 'Design Patterns', type: BookType.CIRCULATING },
        { id: uuid(), isbn: '978-0-321-12521-7', title: 'Domain-Driven Design', type: BookType.RESTRICTED },
        { id: uuid(), isbn: '978-0-13-468599-1', title: 'The Pragmatic Programmer', type: BookType.CIRCULATING },
    ];

    for (const book of books) {
        const result = await libraryService.addBook(book.id, book.isbn, book.title, book.type, branchId);
        if (result.success) {
            console.log(`  ✓ Added: "${book.title}" (${book.type})`);
        }
    }

    // Create patrons
    console.log('\nCreating patrons...\n');

    const regularPatron = {
        id: uuid(),
        name: 'Alice Reader',
        email: 'alice@library.com',
        type: PatronType.REGULAR
    };

    const researcher = {
        id: uuid(),
        name: 'Dr. Bob Scholar',
        email: 'bob@university.edu',
        type: PatronType.RESEARCHER
    };

    await libraryService.createPatron(regularPatron.id, regularPatron.type, regularPatron.name, regularPatron.email);
    console.log(`  ✓ Created regular patron: ${regularPatron.name}`);

    await libraryService.createPatron(researcher.id, researcher.type, researcher.name, researcher.email);
    console.log(`  ✓ Created researcher: ${researcher.name}`);

    // Demonstrate workflows
    console.log('\n--- Demonstrating Library Workflows ---\n');

    // Regular patron places hold and checks out
    console.log('1. Regular patron workflow:');
    const cleanCode = books[0];

    let result = await libraryService.placeHold(cleanCode.id, regularPatron.id, HoldType.CLOSED_ENDED);
    console.log(`   • ${regularPatron.name} places hold on "${cleanCode.title}": ${result.success ? 'Success' : result.error}`);

    result = await libraryService.checkout(cleanCode.id, regularPatron.id);
    console.log(`   • ${regularPatron.name} checks out "${cleanCode.title}": ${result.success ? 'Success' : result.error}`);
    if (result.success) {
        console.log(`   • Due date: ${new Date(result.dueDate).toLocaleDateString()}`);
    }

    // Researcher accesses restricted book with open-ended hold
    console.log('\n2. Researcher workflow (restricted book + open-ended hold):');
    const dddBook = books[2];

    result = await libraryService.placeHold(dddBook.id, researcher.id, HoldType.OPEN_ENDED);
    console.log(`   • ${researcher.name} places open-ended hold on "${dddBook.title}": ${result.success ? 'Success' : result.error}`);

    // Regular patron tries restricted book (should fail)
    console.log('\n3. Regular patron tries restricted book:');
    result = await libraryService.placeHold(dddBook.id, regularPatron.id, HoldType.CLOSED_ENDED);
    console.log(`   • ${regularPatron.name} tries "${dddBook.title}": ${result.success ? 'Success' : result.error}`);

    // Return book
    console.log('\n4. Return workflow:');
    result = await libraryService.returnBook(cleanCode.id, regularPatron.id);
    console.log(`   • ${regularPatron.name} returns "${cleanCode.title}": ${result.success ? 'Success' : result.error}`);

    // Show final state
    console.log('\n--- Final Book States ---\n');
    for (const book of books) {
        const details = await libraryService.getBook(book.id);
        if (details.success) {
            console.log(`  "${details.book.title}": ${details.book.state}`);
        }
    }

    // Show patron summaries
    console.log('\n--- Patron Summaries ---\n');
    const aliceDetails = await libraryService.getPatron(regularPatron.id);
    const bobDetails = await libraryService.getPatron(researcher.id);

    console.log(`  ${regularPatron.name}:`);
    console.log(`    Type: ${aliceDetails.patron.patronType}`);
    console.log(`    Holds: ${aliceDetails.patron.holdsCount}`);
    console.log(`    Checkouts: ${aliceDetails.patron.checkoutsCount}`);

    console.log(`\n  ${researcher.name}:`);
    console.log(`    Type: ${bobDetails.patron.patronType}`);
    console.log(`    Holds: ${bobDetails.patron.holdsCount}`);
    console.log(`    Checkouts: ${bobDetails.patron.checkoutsCount}`);

    console.log('\n✅ Library application demo complete!\n');
    console.log('Run "npm test" to execute the full test suite.\n');
}

main().catch(console.error);
