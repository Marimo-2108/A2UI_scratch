// Writes the a2uiClientCapabilities this browser would send (incl. our custom catalog as an
// INLINE JSON Schema) to ../agent/fixtures/inline_caps.json, so the agent can be tested from
// the command line:   npm run export:caps  &&  uv run python try_agent.py --caps "a KPI dashboard"
//
// Run with Node's built-in TypeScript support (imports a .ts file directly).
import { mkdirSync, writeFileSync } from 'node:fs';
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

const out = new URL('../../agent/fixtures/inline_caps.json', import.meta.url);
mkdirSync(new URL('./', out), { recursive: true });
writeFileSync(out, JSON.stringify(caps, null, 1));
console.log(`wrote ${out.pathname} (${JSON.stringify(caps).length} chars), catalogs:`,
  caps['v0.9'].supportedCatalogIds);

// DESIGN B: the agent's own copy of the catalog, GENERATED from the same Zod source of truth.
// The agent loads it with CatalogConfig.from_path(...) and the browser then sends only the id.
// Never edit this file by hand; re-run `npm run export:caps` after changing a component.
const catalogOut = new URL('../../agent/fixtures/stats-v1.catalog.json', import.meta.url);
writeFileSync(catalogOut, JSON.stringify(caps['v0.9'].inlineCatalogs[0], null, 1));
console.log(`wrote ${catalogOut.pathname}`);
