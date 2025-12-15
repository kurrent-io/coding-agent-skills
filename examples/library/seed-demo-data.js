/**
 * Seed Demo Data for Library Application
 *
 * Populates the library with sample books and patrons
 */

const API_BASE = 'http://localhost:3000/api';

async function post(endpoint, data) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    return response.json();
}

async function seedData() {
    console.log('🌱 Seeding demo data...\n');

    // === BOOKS ===
    console.log('📚 Adding books...\n');

    const books = [
        // Programming & Software Engineering
        { title: 'Clean Code', isbn: '978-0-13-235088-4', bookType: 'Circulating' },
        { title: 'The Pragmatic Programmer', isbn: '978-0-13-595705-9', bookType: 'Circulating' },
        { title: 'Design Patterns', isbn: '978-0-201-63361-0', bookType: 'Circulating' },
        { title: 'Refactoring', isbn: '978-0-13-475759-9', bookType: 'Circulating' },
        { title: 'Domain-Driven Design', isbn: '978-0-321-12521-7', bookType: 'Restricted' },

        // Architecture
        { title: 'Building Microservices', isbn: '978-1-492-03402-5', bookType: 'Circulating' },
        { title: 'Designing Data-Intensive Applications', isbn: '978-1-449-37332-0', bookType: 'Restricted' },
        { title: 'Software Architecture: The Hard Parts', isbn: '978-1-492-08689-5', bookType: 'Circulating' },

        // Event Sourcing & CQRS
        { title: 'Implementing Domain-Driven Design', isbn: '978-0-321-83457-7', bookType: 'Restricted' },
        { title: 'Event Sourcing & CQRS', isbn: '978-0-000-00001-1', bookType: 'Restricted' },

        // Databases
        { title: 'Database Internals', isbn: '978-1-492-04034-7', bookType: 'Circulating' },
        { title: 'NoSQL Distilled', isbn: '978-0-321-82662-6', bookType: 'Circulating' },

        // General Programming
        { title: 'Structure and Interpretation of Computer Programs', isbn: '978-0-262-51087-5', bookType: 'Restricted' },
        { title: 'The Art of Computer Programming Vol. 1', isbn: '978-0-201-89683-1', bookType: 'Restricted' },
        { title: 'Introduction to Algorithms', isbn: '978-0-262-04630-5', bookType: 'Circulating' },

        // DevOps & Cloud
        { title: 'The Phoenix Project', isbn: '978-1-942788-29-4', bookType: 'Circulating' },
        { title: 'Accelerate', isbn: '978-1-942788-33-1', bookType: 'Circulating' },
        { title: 'Site Reliability Engineering', isbn: '978-1-491-92912-4', bookType: 'Circulating' },

        // Testing
        { title: 'Test Driven Development', isbn: '978-0-321-14653-3', bookType: 'Circulating' },
        { title: 'Growing Object-Oriented Software', isbn: '978-0-321-50362-6', bookType: 'Circulating' },
    ];

    const addedBooks = [];
    for (const book of books) {
        const result = await post('/books', book);
        if (result.success) {
            console.log(`  ✓ ${book.title} (${book.bookType})`);
            addedBooks.push({ ...book, bookId: result.bookId });
        } else {
            console.log(`  ✗ ${book.title}: ${result.error}`);
        }
    }

    // === PATRONS ===
    console.log('\n👥 Adding patrons...\n');

    const patrons = [
        // Regular patrons
        { name: 'Alice Johnson', email: 'alice.johnson@email.com', patronType: 'Regular' },
        { name: 'Bob Smith', email: 'bob.smith@email.com', patronType: 'Regular' },
        { name: 'Carol Williams', email: 'carol.williams@email.com', patronType: 'Regular' },
        { name: 'David Brown', email: 'david.brown@email.com', patronType: 'Regular' },
        { name: 'Eva Martinez', email: 'eva.martinez@email.com', patronType: 'Regular' },
        { name: 'Frank Lee', email: 'frank.lee@email.com', patronType: 'Regular' },

        // Researchers
        { name: 'Dr. Grace Chen', email: 'grace.chen@university.edu', patronType: 'Researcher' },
        { name: 'Prof. Henry Wilson', email: 'henry.wilson@university.edu', patronType: 'Researcher' },
        { name: 'Dr. Isabella Garcia', email: 'isabella.garcia@research.org', patronType: 'Researcher' },
        { name: 'Dr. James Taylor', email: 'james.taylor@institute.edu', patronType: 'Researcher' },
    ];

    const addedPatrons = [];
    for (const patron of patrons) {
        const result = await post('/patrons', patron);
        if (result.success) {
            console.log(`  ✓ ${patron.name} (${patron.patronType})`);
            addedPatrons.push({ ...patron, patronId: result.patronId });
        } else {
            console.log(`  ✗ ${patron.name}: ${result.error}`);
        }
    }

    // === SAMPLE INTERACTIONS ===
    console.log('\n📖 Creating sample interactions...\n');

    // Find specific books and patrons for interactions
    const cleanCode = addedBooks.find(b => b.title === 'Clean Code');
    const pragmaticProgrammer = addedBooks.find(b => b.title === 'The Pragmatic Programmer');
    const ddd = addedBooks.find(b => b.title === 'Domain-Driven Design');
    const microservices = addedBooks.find(b => b.title === 'Building Microservices');
    const phoenixProject = addedBooks.find(b => b.title === 'The Phoenix Project');

    const alice = addedPatrons.find(p => p.name === 'Alice Johnson');
    const bob = addedPatrons.find(p => p.name === 'Bob Smith');
    const drGrace = addedPatrons.find(p => p.name === 'Dr. Grace Chen');
    const profHenry = addedPatrons.find(p => p.name === 'Prof. Henry Wilson');

    // Alice places hold on Clean Code
    if (cleanCode && alice) {
        const holdResult = await post(`/books/${cleanCode.bookId}/hold`, {
            patronId: alice.patronId,
            holdType: 'ClosedEnded'
        });
        if (holdResult.success) {
            console.log(`  ✓ ${alice.name} placed hold on "${cleanCode.title}"`);
        }
    }

    // Bob places hold and checks out Pragmatic Programmer
    if (pragmaticProgrammer && bob) {
        const holdResult = await post(`/books/${pragmaticProgrammer.bookId}/hold`, {
            patronId: bob.patronId,
            holdType: 'ClosedEnded'
        });
        if (holdResult.success) {
            console.log(`  ✓ ${bob.name} placed hold on "${pragmaticProgrammer.title}"`);

            const checkoutResult = await post(`/books/${pragmaticProgrammer.bookId}/checkout`, {
                patronId: bob.patronId
            });
            if (checkoutResult.success) {
                console.log(`  ✓ ${bob.name} checked out "${pragmaticProgrammer.title}"`);
            }
        }
    }

    // Dr. Grace places open-ended hold on restricted DDD book
    if (ddd && drGrace) {
        const holdResult = await post(`/books/${ddd.bookId}/hold`, {
            patronId: drGrace.patronId,
            holdType: 'OpenEnded'
        });
        if (holdResult.success) {
            console.log(`  ✓ ${drGrace.name} placed open-ended hold on "${ddd.title}" (Restricted)`);
        }
    }

    // Prof. Henry checks out Microservices book
    if (microservices && profHenry) {
        const holdResult = await post(`/books/${microservices.bookId}/hold`, {
            patronId: profHenry.patronId,
            holdType: 'ClosedEnded'
        });
        if (holdResult.success) {
            const checkoutResult = await post(`/books/${microservices.bookId}/checkout`, {
                patronId: profHenry.patronId
            });
            if (checkoutResult.success) {
                console.log(`  ✓ ${profHenry.name} checked out "${microservices.title}"`);
            }
        }
    }

    // Alice also places hold on Phoenix Project
    if (phoenixProject && alice) {
        const holdResult = await post(`/books/${phoenixProject.bookId}/hold`, {
            patronId: alice.patronId,
            holdType: 'ClosedEnded'
        });
        if (holdResult.success) {
            console.log(`  ✓ ${alice.name} placed hold on "${phoenixProject.title}"`);
        }
    }

    // === SUMMARY ===
    console.log('\n' + '='.repeat(50));
    console.log('📊 Demo Data Summary');
    console.log('='.repeat(50));
    console.log(`  Books added: ${addedBooks.length}`);
    console.log(`    - Circulating: ${addedBooks.filter(b => b.bookType === 'Circulating').length}`);
    console.log(`    - Restricted: ${addedBooks.filter(b => b.bookType === 'Restricted').length}`);
    console.log(`  Patrons added: ${addedPatrons.length}`);
    console.log(`    - Regular: ${addedPatrons.filter(p => p.patronType === 'Regular').length}`);
    console.log(`    - Researcher: ${addedPatrons.filter(p => p.patronType === 'Researcher').length}`);
    console.log('\n  Sample interactions created:');
    console.log('    - 3 books on hold');
    console.log('    - 2 books checked out');
    console.log('\n✅ Demo data seeded successfully!');
    console.log('\n🌐 Open http://localhost:3000 to view the library\n');
}

seedData().catch(console.error);
