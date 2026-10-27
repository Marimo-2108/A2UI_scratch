// Writes the backend's A2UI catalog (basic components + StatCard) to
// ../Backend/fixtures/stats-v1.catalog.json, GENERATED from the same Zod source the browser uses.
// The agent validates its UI against this file. Never edit it by hand; re-run
// `npm run export:caps` after changing a component, then restart the backend.
//
// Run with Node's built-in TypeScript support (imports a .ts file directly).
import { writeFileSync } from 'node:fs';
import { Catalog, MessageProcessor } from '@a2ui/web_core/v0_9';
import { basicCatalog, BASIC_FUNCTIONS } from '@a2ui/web_core/v0_9/basic_catalog';
import { statCardApi } from '../src/catalog/statCardApi.ts';

// Same recipe as src/catalog/myCatalog.ts, but schema-only (no React needed for the export).
const MY_CATALOG_ID = 'https://scratch.local/a2ui/catalogs/stats-v1.json';
const catalog = new Catalog(
  MY_CATALOG_ID,
  '0.9',
  [...basicCatalog.components.values(), statCardApi],
  BASIC_FUNCTIONS,
  basicCatalog.themeSchema,
);

const caps = new MessageProcessor([catalog]).getRendererCapabilities({
  versions: ['v0.9'],
  includeInlineCatalogs: true,
});

const catalogOut = new URL('../../Backend/fixtures/stats-v1.catalog.json', import.meta.url);
writeFileSync(catalogOut, JSON.stringify(caps['v0.9'].inlineCatalogs[0], null, 1));
console.log(`wrote ${catalogOut.pathname}`);
