/**
 * Milestone 5: our first CUSTOM component, API half.
 *
 * A2UI v0.9 splits a component into
 *   - the API   (this file): name + a Zod schema of its properties. Pure data, no React.
 *   - the implementation (StatCard.tsx): how it looks.
 *
 * The API is what the AGENT learns about (exported as JSON Schema into the LLM prompt);
 * the implementation never leaves the browser. That split is the security model:
 * the model can only ask for "StatCard" with these properties, never ship code.
 */
import { z } from 'zod';
import { DynamicStringSchema, type ComponentApi } from '@a2ui/web_core/v0_9';

export const statCardApi = {
  name: 'StatCard',
  schema: z.object({
    label: DynamicStringSchema.describe('Short name of the metric, e.g. "Monthly revenue".'),
    value: DynamicStringSchema.describe('The headline number, already formatted, e.g. "$48.2k".'),
    change: DynamicStringSchema.optional().describe('Change vs. before, e.g. "+12%".'),
    trend: z
      .enum(['up', 'down', 'flat'])
      .optional()
      .describe(
        'Direction of the change; drives the colour and arrow. LITERAL ONLY: exactly "up", "down" ' +
          'or "flat". It can NOT be a data binding ({"path": ...}) or a function call.',
      ),
  }),
} satisfies ComponentApi;
