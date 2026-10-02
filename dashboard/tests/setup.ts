import '@testing-library/jest-dom/vitest';
import { configure } from '@testing-library/react';
import { vi } from 'vitest';

// Route chunks are lazy-loaded in the app; allow async queries enough time.
configure({ asyncUtilTimeout: process.platform === 'win32' ? 15000 : 5000 });
// jsdom has no viewport; scrolling is a browser effect, not a test assertion.
window.scrollTo = vi.fn();
