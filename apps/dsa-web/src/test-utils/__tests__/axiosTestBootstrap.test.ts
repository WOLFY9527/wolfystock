import axios from 'axios';
import { expect, it } from 'vitest';

it('preloads the real Axios module before test-file async-leak ownership begins', () => {
  expect(axios.create).toBeTypeOf('function');
});
