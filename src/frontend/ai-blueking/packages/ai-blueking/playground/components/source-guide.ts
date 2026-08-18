export interface SourceGuideBlock {
  code?: string;
  desc?: string;
  fileHint?: string;
  title: string;
}

export interface SourceGuideSection {
  blocks?: SourceGuideBlock[];
  id: string;
  label: string;
  notes?: string[];
}
