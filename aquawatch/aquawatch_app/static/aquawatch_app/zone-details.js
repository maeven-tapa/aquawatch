export function zoneDateLabel(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return 'Date unavailable';
  return new Intl.DateTimeFormat('en-PH', {year:'numeric',month:'long',day:'numeric',timeZone:'UTC'}).format(new Date(`${value}T00:00:00Z`));
}

export function publicationLabel(zone) {
  if (!zone.active) return 'Unpublished';
  if (!zone.published_at) return 'Publication date unavailable for this older zone';
  const published = new Date(zone.published_at);
  if (!Number.isFinite(published.getTime())) return 'Publication date unavailable';
  return `First published: ${new Intl.DateTimeFormat('en-PH', {year:'numeric',month:'long',day:'numeric',hour:'numeric',minute:'2-digit',timeZone:'Asia/Manila'}).format(published)} (Philippine time)`;
}

export function recurrenceLabel(zone) {
  return zone.repeats_annually ? `Repeats every year · Original zone date: ${zoneDateLabel(zone.date)}` : 'Applies to this year only';
}
