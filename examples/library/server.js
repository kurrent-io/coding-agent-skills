/**
 * Library Web Server
 *
 * Express API server for the Library DDD application
 */

import express from 'express';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { v4 as uuid } from 'uuid';
import { LibraryService } from './application/library-service.js';
import { PatronType, BookType, HoldType } from './domain/events.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(express.json());
app.use(express.static(join(__dirname, 'public')));

// Initialize library service
const libraryService = new LibraryService();

// In-memory indexes for listing (in production, use read models)
const booksIndex = new Map();
const patronsIndex = new Map();

// === API Routes ===

// Health check
app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// === Books ===

// List all books
app.get('/api/books', async (req, res) => {
    try {
        const books = [];
        for (const bookId of booksIndex.keys()) {
            const result = await libraryService.getBook(bookId);
            if (result.success) {
                books.push(result.book);
            }
        }
        res.json({ success: true, books });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// Get single book
app.get('/api/books/:bookId', async (req, res) => {
    try {
        const result = await libraryService.getBook(req.params.bookId);
        if (result.success) {
            res.json(result);
        } else {
            res.status(404).json(result);
        }
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// Add a new book
app.post('/api/books', async (req, res) => {
    try {
        const { isbn, title, bookType, libraryBranchId } = req.body;
        const bookId = uuid();

        const result = await libraryService.addBook(
            bookId,
            isbn || `978-${Date.now()}`,
            title,
            bookType || BookType.CIRCULATING,
            libraryBranchId || 'main-branch'
        );

        if (result.success) {
            booksIndex.set(bookId, { title, bookType });
            res.status(201).json({ ...result, bookId });
        } else {
            res.status(400).json(result);
        }
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// Place hold on book
app.post('/api/books/:bookId/hold', async (req, res) => {
    try {
        const { patronId, holdType } = req.body;
        const result = await libraryService.placeHold(
            req.params.bookId,
            patronId,
            holdType || HoldType.CLOSED_ENDED
        );

        if (result.success) {
            res.json(result);
        } else {
            res.status(400).json(result);
        }
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// Cancel hold
app.delete('/api/books/:bookId/hold', async (req, res) => {
    try {
        const { patronId, reason } = req.body;
        const result = await libraryService.cancelHold(
            req.params.bookId,
            patronId,
            reason || 'Canceled via UI'
        );

        if (result.success) {
            res.json(result);
        } else {
            res.status(400).json(result);
        }
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// Checkout book
app.post('/api/books/:bookId/checkout', async (req, res) => {
    try {
        const { patronId } = req.body;
        const result = await libraryService.checkout(req.params.bookId, patronId);

        if (result.success) {
            res.json(result);
        } else {
            res.status(400).json(result);
        }
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// Return book
app.post('/api/books/:bookId/return', async (req, res) => {
    try {
        const { patronId } = req.body;
        const result = await libraryService.returnBook(req.params.bookId, patronId);

        if (result.success) {
            res.json(result);
        } else {
            res.status(400).json(result);
        }
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// === Patrons ===

// List all patrons
app.get('/api/patrons', async (req, res) => {
    try {
        const patrons = [];
        for (const patronId of patronsIndex.keys()) {
            const result = await libraryService.getPatron(patronId);
            if (result.success) {
                patrons.push(result.patron);
            }
        }
        res.json({ success: true, patrons });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// Get single patron
app.get('/api/patrons/:patronId', async (req, res) => {
    try {
        const result = await libraryService.getPatron(req.params.patronId);
        if (result.success) {
            res.json(result);
        } else {
            res.status(404).json(result);
        }
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// Create patron
app.post('/api/patrons', async (req, res) => {
    try {
        const { name, email, patronType } = req.body;
        const patronId = uuid();

        const result = await libraryService.createPatron(
            patronId,
            patronType || PatronType.REGULAR,
            name,
            email
        );

        if (result.success) {
            patronsIndex.set(patronId, { name, patronType });
            res.status(201).json({ ...result, patronId });
        } else {
            res.status(400).json(result);
        }
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// Upgrade patron to researcher
app.post('/api/patrons/:patronId/upgrade', async (req, res) => {
    try {
        const result = await libraryService.upgradePatronToResearcher(req.params.patronId);

        if (result.success) {
            res.json(result);
        } else {
            res.status(400).json(result);
        }
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// Serve the frontend
app.get('/', (req, res) => {
    res.sendFile(join(__dirname, 'public', 'index.html'));
});

// Start server
app.listen(PORT, () => {
    console.log(`\n📚 Library Server running at http://localhost:${PORT}`);
    console.log(`   API endpoints available at http://localhost:${PORT}/api`);
    console.log(`   KurrentDB UI at http://localhost:2113\n`);
});

export { app };
