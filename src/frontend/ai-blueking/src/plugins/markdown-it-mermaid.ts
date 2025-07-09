import mermaid from "mermaid";

// Define interface to await readiness of import
export default function mermaidPlugin(md: any, options: any = {}) {
  // Setup Mermaid with default options for v10.x
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "loose",
    theme: "default",
    ...options,
  });

  function getLangName(info: string): string {
    return info.split(/\s+/g)[0];
  }

  // Store reference to original renderer.
  let defaultFenceRenderer = md.renderer.rules.fence;

  // Since mermaid rendering is async in v10.x, we need to handle this differently
  // We'll create a synchronous wrapper that handles the async rendering
  function syncFenceRenderer(
    tokens: any[],
    idx: number,
    options: any,
    env: any,
    slf: any
  ) {
    let token = tokens[idx];
    let info = token.info.trim();
    let langName = info ? getLangName(info) : "";

    if (["mermaid", "{mermaid}"].indexOf(langName) === -1) {
      if (defaultFenceRenderer !== undefined) {
        return defaultFenceRenderer(tokens, idx, options, env, slf);
      }
      return "";
    }

    // Generate unique ID for this diagram
    const diagramId = `mermaid-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
    
    // Return a placeholder that will be replaced by the actual SVG
    // We'll use a data attribute to store the mermaid content
    return `<div class="mermaid-placeholder" data-mermaid-id="${diagramId}" data-mermaid-content="${encodeURIComponent(token.content)}">Loading diagram...</div>`;
  }

  md.renderer.rules.fence = syncFenceRenderer;
}
