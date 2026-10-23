/**
 * Our own catalog = the basic components + StatCard, under OUR catalog id.
 *
 * The id is just an agreed-upon string (see docs/01). A new id means the agent can tell
 * "this client can draw StatCard" apart from "this client only has the basic components".
 */
import { Catalog } from '@a2ui/web_core/v0_9';
import { basicCatalog, BASIC_FUNCTIONS } from '@a2ui/web_core/v0_9/basic_catalog';
import type { ReactCatalogComponent } from '@a2ui/react/v0_9';
import { StatCard } from './StatCard';

export const MY_CATALOG_ID = 'https://scratch.local/a2ui/catalogs/stats-v1.json';

export const myCatalog = new Catalog<ReactCatalogComponent>(
  MY_CATALOG_ID,
  '0.9',
  [...(basicCatalog.components.values() as Iterable<ReactCatalogComponent>), StatCard],
  BASIC_FUNCTIONS,
  basicCatalog.themeSchema,
);
