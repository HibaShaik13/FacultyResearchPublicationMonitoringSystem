/**
 * Normalizes agent and service names for user-facing presentation.
 * Strips internal agent/phase numbers and formats human-readable labels.
 */
export function cleanServiceName(name: string): string {
  if (!name) return name;
  let cleaned = name;

  // Remove internal agent numbering patterns like "(Agent 13)", "Agent 8:", "Agent 10", "Agents 1–12"
  cleaned = cleaned.replace(/\s*\(Agent\s*\d+\)/gi, '');
  cleaned = cleaned.replace(/\bAgent\s*\d+:\s*/gi, '');
  cleaned = cleaned.replace(/\bAgent\s*\d+\b/gi, '');
  cleaned = cleaned.replace(/\bAgents\s*\d+([–-]\d+)?\b/gi, '');
  cleaned = cleaned.replace(/\bPhase\s*\d+:\s*/gi, '');
  cleaned = cleaned.replace(/\bPhase\s*\d+\b/gi, '');

  // Map specific agent names to clean human-readable services
  const lower = cleaned.toLowerCase().trim();
  if (lower.includes('human review')) return 'Human Review & Verification';
  if (lower.includes('reporting')) return 'Reporting & Accreditation';
  if (lower.includes('research assistant') || lower.includes('intelligence assistant')) {
    return 'Research Intelligence Assistant';
  }
  if (lower.includes('faculty identity')) return 'Faculty Identity';
  if (lower.includes('publication discovery')) return 'Publication Discovery';
  if (lower.includes('affiliation intelligence')) return 'Affiliation Intelligence';
  if (lower.includes('deduplication')) return 'Deduplication';
  if (lower.includes('faculty attribution')) return 'Faculty Attribution';
  if (lower.includes('metadata normalization')) return 'Metadata Normalization';
  if (lower.includes('metadata enrichment')) return 'Metadata Enrichment';
  if (lower.includes('research integrity')) return 'Research Integrity';
  if (lower.includes('citation metrics')) return 'Citation Metrics';
  if (lower.includes('verification') && lower.includes('evidence')) return 'Verification & Evidence';

  // Strip trailing "Agent" from presentation if present
  cleaned = cleaned.replace(/\s+Agent$/i, '');
  return cleaned.trim();
}
