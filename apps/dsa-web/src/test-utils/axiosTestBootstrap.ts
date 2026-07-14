/**
 * Load Axios before Vitest starts attributing async resources to a test file.
 * Axios's fetch adapter probes `new Response('').body` during module import.
 * In jsdom, the unread native stream leaves a Promise that Vitest reports as
 * belonging to whichever test file first imports Axios, despite no request.
 */
import 'axios';
