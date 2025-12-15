/**
 * Event Store Repository using KurrentDB
 *
 * Provides aggregate persistence with optimistic concurrency control
 */

import {
    KurrentDBClient,
    jsonEvent,
    FORWARDS,
    START,
    NO_STREAM,
    ANY,
    StreamNotFoundError,
    WrongExpectedVersionError,
} from '@kurrent/kurrentdb-client';
import { v4 as uuid } from 'uuid';

export class EventStore {
    constructor(connectionString = 'kurrentdb://localhost:2113?tls=false') {
        this.client = KurrentDBClient.connectionString(connectionString);
        this.connectionString = connectionString;
    }

    /**
     * Append events to a stream with optimistic concurrency
     * @param {string} streamName
     * @param {Array} events - Array of { type, data } objects
     * @param {number|string} expectedRevision - Expected stream revision or NO_STREAM/ANY
     */
    async appendToStream(streamName, events, expectedRevision = ANY) {
        const eventDataList = events.map(event =>
            jsonEvent({
                id: uuid(),
                type: event.type,
                data: event.data,
                metadata: {
                    timestamp: new Date().toISOString(),
                    correlationId: uuid(),
                }
            })
        );

        try {
            const result = await this.client.appendToStream(
                streamName,
                eventDataList,
                { expectedRevision }
            );
            return {
                success: true,
                nextExpectedRevision: result.nextExpectedRevision,
            };
        } catch (error) {
            if (error instanceof WrongExpectedVersionError) {
                return {
                    success: false,
                    error: 'Concurrency conflict: stream was modified',
                    details: error.message,
                };
            }
            throw error;
        }
    }

    /**
     * Read all events from a stream
     * @param {string} streamName
     * @returns {Array} Array of events with type and data
     */
    async readStream(streamName) {
        try {
            const events = [];
            const readResult = this.client.readStream(streamName, {
                direction: FORWARDS,
                fromRevision: START,
                maxCount: 1000,
            });

            for await (const resolvedEvent of readResult) {
                if (resolvedEvent.event) {
                    events.push({
                        eventId: resolvedEvent.event.id,
                        type: resolvedEvent.event.type,
                        data: resolvedEvent.event.data,
                        metadata: resolvedEvent.event.metadata,
                        revision: resolvedEvent.event.revision,
                        created: resolvedEvent.event.created,
                    });
                }
            }

            return { success: true, events };
        } catch (error) {
            if (error instanceof StreamNotFoundError || error.type === 'stream-not-found') {
                return { success: true, events: [], notFound: true };
            }
            throw error;
        }
    }

    /**
     * Check if a stream exists
     */
    async streamExists(streamName) {
        const result = await this.readStream(streamName);
        return !result.notFound && result.events.length > 0;
    }

    /**
     * Subscribe to a stream for catch-up subscription
     */
    subscribeToStream(streamName, fromRevision = START) {
        return this.client.subscribeToStream(streamName, { fromRevision });
    }

    /**
     * Subscribe to all streams with optional filter
     */
    subscribeToAll(options = {}) {
        return this.client.subscribeToAll(options);
    }

    /**
     * Get current revision of a stream
     */
    async getStreamRevision(streamName) {
        const result = await this.readStream(streamName);
        if (result.notFound || result.events.length === 0) {
            return -1;
        }
        return Number(result.events[result.events.length - 1].revision);
    }
}
