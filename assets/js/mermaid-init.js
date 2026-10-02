// Renders ```mermaid fenced blocks on pages that set `mermaid: true` in
// their front matter. Jekyll emits each block as
// <pre><code class="language-mermaid">source</code></pre>; each one is
// replaced by a wrapper holding the source as text, and Mermaid draws the
// SVG into it.
document.addEventListener('DOMContentLoaded', async () => {
  if (typeof mermaid === 'undefined') return;

  // Sequential ids: the default time-based ids can repeat across diagrams.
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict',
    theme: 'neutral',
    deterministicIds: true,
  });

  const nodes = [];
  document.querySelectorAll('code.language-mermaid').forEach((code) => {
    const block = code.closest('pre');
    if (!block) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'mermaid-diagram';
    wrapper.textContent = code.textContent;
    block.replaceWith(wrapper);
    nodes.push(wrapper);
  });

  await mermaid.run({ nodes });
});
