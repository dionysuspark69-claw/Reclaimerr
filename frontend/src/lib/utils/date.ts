/**
 * Formats a date string into a more readable format.
 * @param dateString The date string to format.
 * @returns A formatted date string.
 */
const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
};

/**
 * Formats a date string into a relative time format (e.g., "2 days ago" or "in 3 hours").
 * @param dateString The date string to format.
 * @returns A formatted relative time string.
 */
const formatDistanceToNow = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const isFuture = diffMs < 0;
  const absDiffMs = Math.abs(diffMs);

  const seconds = Math.floor(absDiffMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  let result = "";
  if (days > 0) {
    result = `${days} day${days > 1 ? "s" : ""}`;
  } else if (hours > 0) {
    result = `${hours} hour${hours > 1 ? "s" : ""}`;
  } else if (minutes > 0) {
    result = `${minutes} minute${minutes > 1 ? "s" : ""}`;
  } else {
    result = `${seconds} second${seconds > 1 ? "s" : ""}`;
  }

  return isFuture ? `in ${result}` : `${result} ago`;
};

/**
 * Formats a date string into a locale-specific date string. If the input is null, it returns "Unknown".
 * @param dateStr The date string to format.
 * @returns A formatted date string in the locale-specific format, or "Unknown" if the input is null.
 */
const formatDateToLocaleString = (dateStr: string | null): string => {
  if (!dateStr) return "Unknown";
  try {
    return new Date(dateStr).toLocaleDateString();
  } catch {
    return dateStr;
  }
};

export { formatDate, formatDistanceToNow, formatDateToLocaleString };
