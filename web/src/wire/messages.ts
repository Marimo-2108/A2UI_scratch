import { basicCatalog } from '@a2ui/web_core/v0_9/basic_catalog';

/**
 * Milestone 1: a hand-written "wire" - the exact JSON an agent would stream.
 *
 * Nothing here is generated. Read each message, then step through them in the
 * UI and watch what changes. Shapes follow specification/v0_9_1/docs/a2ui_protocol.md
 *
 * The 4 server -> client message types:
 *   createSurface | updateComponents | updateDataModel | deleteSurface
 */

export const SURFACE_ID = 'welcome_card';

// Catalog IDs are just agreed-upon strings, matched EXACTLY. The client registers a catalog
// under an ID; the agent must name that same ID. This library's basic catalog is registered
// under the v0_9 URL (not v0_9_1), so we read it from the catalog itself.
export const BASIC_CATALOG_ID = basicCatalog.id;

export interface WireStep {
  /** Short label shown in the step list. */
  title: string;
  /** What you should observe after this step. */
  explain: string;
  /** The raw message, exactly as it would travel over the transport. */
  message: Record<string, unknown>;
}

export const wire: WireStep[] = [
  {
    title: '1. createSurface',
    explain:
      'Creates an empty surface bound to a catalog. Nothing is visible yet: there is no root component.',
    message: {
      version: 'v0.9.1',
      createSurface: { surfaceId: SURFACE_ID, catalogId: BASIC_CATALOG_ID },
    },
  },
  {
    title: '2. updateComponents (structure)',
    explain:
      'A FLAT list of components. The tree is made by id references (children: [...]). The component with id "root" is the entry point. Text values here come from the data model via {path}, which is still empty, so they render blank.',
    message: {
      version: 'v0.9.1',
      updateComponents: {
        surfaceId: SURFACE_ID,
        components: [
          { id: 'root', component: 'Card', child: 'content' },
          {
            id: 'content',
            component: 'Column',
            children: ['title', 'greeting', 'name_input', 'submit_label_btn'],
          },
          { id: 'title', component: 'Text', variant: 'h2', text: { path: '/title' } },
          { id: 'greeting', component: 'Text', text: { path: '/greeting' } },
          {
            id: 'name_input',
            component: 'TextField',
            label: 'Your name',
            value: { path: '/name' },
          },
          { id: 'submit_label', component: 'Text', text: 'Send my name to the agent' },
          {
            id: 'submit_label_btn',
            component: 'Button',
            variant: 'primary',
            child: 'submit_label',
            action: {
              event: {
                name: 'submit_name',
                // context values can be bound to the data model too
                context: { name: { path: '/name' } },
              },
            },
          },
        ],
      },
    },
  },
  {
    title: '3. updateDataModel (content)',
    explain:
      'Structure and data are separate. Now the paths resolve and the text appears. The agent can update data later WITHOUT resending the components.',
    message: {
      version: 'v0.9.1',
      updateDataModel: {
        surfaceId: SURFACE_ID,
        path: '/',
        value: {
          title: 'Hello from the wire',
          greeting: 'This card was built from 3 JSON messages.',
          name: '',
        },
      },
    },
  },
  {
    title: '4. updateDataModel (partial)',
    explain:
      'Replace a single value at a JSON Pointer path. Only the greeting text re-renders; components are untouched.',
    message: {
      version: 'v0.9.1',
      updateDataModel: {
        surfaceId: SURFACE_ID,
        path: '/greeting',
        value: 'Only this line changed. Same components, new data.',
      },
    },
  },
  {
    title: '5. updateComponents (patch)',
    explain:
      'Components are upserted by id. Re-sending "title" with new props patches it in place; everything else stays.',
    message: {
      version: 'v0.9.1',
      updateComponents: {
        surfaceId: SURFACE_ID,
        components: [
          { id: 'title', component: 'Text', variant: 'h1', text: { path: '/title' } },
        ],
      },
    },
  },
  {
    title: '6. deleteSurface',
    explain: 'Removes the surface and its data model from the client.',
    message: {
      version: 'v0.9.1',
      deleteSurface: { surfaceId: SURFACE_ID },
    },
  },
];
