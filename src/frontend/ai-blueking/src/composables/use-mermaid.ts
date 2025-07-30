import { nextTick } from 'vue';
import mermaid from 'mermaid';
import DOMPurify from 'dompurify';

export function useMermaid() {
  // Initialize mermaid with v10.x configuration
  const initMermaid = () => {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'loose',
      theme: 'default',
      fontFamily: 'Arial, sans-serif',
      fontSize: 14,
    });
  };

  // Render mermaid diagrams in the given container
  const renderMermaidDiagrams = async (container: HTMLElement) => {
    const placeholders = container.querySelectorAll('.mermaid-placeholder');

    for (const placeholder of placeholders) {
      try {
        const diagramId = placeholder.getAttribute('data-mermaid-id');
        const encodedContent = placeholder.getAttribute('data-mermaid-content');

        if (!diagramId || !encodedContent) {
          continue;
        }

        const content = decodeURIComponent(encodedContent);

        // Use mermaid v10.x render method - this will create a temporary element in body
        const { svg } = await mermaid.render(diagramId, content);

        // Clean up any temporary elements that mermaid might have created in body
        const tempElement = document.getElementById(`d${diagramId}`);
        if (tempElement) {
          tempElement.remove();
        }

        // Create wrapper div with proper styling
        const wrapper = document.createElement('div');
        const cleanSvg = DOMPurify.sanitize(svg, {ADD_TAGS: ['foreignObject'], USE_PROFILES: {svg: true, svgFilters: true}});
        wrapper.className = 'mermaid-diagram';
        wrapper.innerHTML = cleanSvg;

        // Replace placeholder with rendered diagram
        placeholder.parentNode?.replaceChild(wrapper, placeholder);
      } catch (error) {
        console.error('Mermaid rendering error:', error);

        // Clean up any temporary elements on error
        const diagramId = placeholder.getAttribute('data-mermaid-id');
        if (diagramId) {
          const tempElement = document.getElementById(`d${diagramId}`);
          if (tempElement) {
            tempElement.remove();
          }
        }

        // Show error message
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger mermaid-error';
        const errorMessage = error instanceof Error ? error.message : String(error);
        errorDiv.textContent = `Mermaid diagram error: ${errorMessage}`;

        placeholder.parentNode?.replaceChild(errorDiv, placeholder);
      }
    }
  };

  // Process mermaid diagrams after DOM update
  const processMermaidDiagrams = async (element: HTMLElement, onComplete?: () => void) => {
    await nextTick();
    await renderMermaidDiagrams(element);

    // 在 mermaid 渲染完成后，再次等待 DOM 更新，然后执行回调
    await nextTick();
    if (onComplete) {
      onComplete();
    }
  };

  // Clean up any temporary mermaid elements in the body
  const cleanupMermaidElements = () => {
    // Remove any temporary divs that mermaid might have created
    const tempElements = document.querySelectorAll('[id^="dmermaid-"]');
    tempElements.forEach(element => element.remove());
  };

  return {
    initMermaid,
    renderMermaidDiagrams,
    processMermaidDiagrams,
    cleanupMermaidElements,
  };
}
