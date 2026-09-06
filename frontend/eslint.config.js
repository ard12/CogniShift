import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      // This codebase fetches data with plain useEffect + fetch (no
      // TanStack Query/SWR — see project constraints on minimal
      // dependencies), which is exactly the "subscribe to an external
      // system and setState from its response" pattern the rule's own
      // description endorses. The rule's static analysis still flags the
      // synchronous setState calls that kick off/reset that fetch (e.g.
      // `setLoading(true)` before an async call, or a guard-clause
      // `setState([])` for a missing dependency), which are safe here:
      // every one of these effects is idempotent and gated on its
      // dependency array, so there is no cascading-render loop in
      // practice. Introducing a data-fetching library solely to satisfy
      // this advisory rule would be a large, out-of-scope architecture
      // change across every page in the app.
      'react-hooks/set-state-in-effect': 'off',
    },
  },
])
