export class ContentError extends Error {
  public readonly details?: Record<string, unknown>;

  public constructor(message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "ContentError";
    this.details = details;
  }
}

export class DuplicateIdError extends ContentError {
  public constructor(kind: string, id: string) {
    super(`${kind} has duplicate id '${id}'.`, { kind, id });
    this.name = "DuplicateIdError";
  }
}

export class MissingReferenceError extends ContentError {
  public constructor(args: {
    sourceType: string;
    sourceId: string;
    fieldPath: string;
    targetType: string;
    targetId: string;
  }) {
    const { sourceType, sourceId, fieldPath, targetType, targetId } = args;
    super(
      `${sourceType}:${sourceId}.${fieldPath} references missing ${targetType} '${targetId}'.`,
      args
    );
    this.name = "MissingReferenceError";
  }
}

export function assertUniqueIds<T extends { id: string }>(kind: string, records: T[]): void {
  const seen = new Set<string>();
  for (const record of records) {
    if (seen.has(record.id)) {
      throw new DuplicateIdError(kind, record.id);
    }
    seen.add(record.id);
  }
}

export function indexById<T extends { id: string }>(records: T[]): Record<string, T> {
  const indexed: Record<string, T> = {};
  for (const record of records) {
    indexed[record.id] = record;
  }
  return indexed;
}

export function assertReferenceExists(args: {
  sourceType: string;
  sourceId: string;
  fieldPath: string;
  targetType: string;
  targetId: string;
  exists: boolean;
}): void {
  if (!args.exists) {
    throw new MissingReferenceError(args);
  }
}
