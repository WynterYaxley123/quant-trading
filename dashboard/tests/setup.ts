import '@testing-library/jest-dom/vitest';
import { configure } from '@testing-library/react';

// Route chunks are lazy-loaded in the app; allow async queries enough time.
configure({ asyncUtilTimeout: 5000 });
