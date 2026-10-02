// Renders ```mermaid fenced blocks on pages that set `mermaid: true` in
// their front matter. Jekyll emits each block as
// <pre><code class="language-mermaid">source</code></pre>; each one is
// replaced by the SVG that Mermaid draws from its source.
document.addEventListener('DOMContentLoaded', async () => {
  if (typeof mermaid === 'undefined') return;

  mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'neutral' });

  const blocks = document.querySelectorAll('code.language-mermaid');
  let index = 0;
  for (const code of blocks) {
    const block = code.closest('pre');
    if (!block) continue;
    index += 1;
    try {
      // Explicit ids: Mermaid's generated ids are time-based and can repeat.
      const { svg } = await mermaid.render('mermaid-diagram-' + index, code.textContent);
      const wrapper = document.createElement('div');
      wrapper.className = 'mermaid-diagram';
      wrapper.innerHTML = svg;
      block.replaceWith(wrapper);
    } catch (err) {
      console.error('Mermaid failed to render diagram ' + index, err);
    }
  }
});
