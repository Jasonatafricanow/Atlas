// Render only the supplied local neighborhood. Destroy on navigation/privacy change.
export function renderGraph(data) {
  const container = document.getElementById('graph');
  if (!container || !globalThis.cytoscape) return () => {};
  const colors = getComputedStyle(document.documentElement);
  const color = name => colors.getPropertyValue(name).trim();
  const number = name => parseFloat(color(name));
  const degrees = new Map(data.nodes.map(n => [n.node_id, 0]));
  for (const edge of data.edges) {
    for (const id of [edge.src, edge.dst]) degrees.set(id, (degrees.get(id) || 0) + 1);
  }
  const maxDegree = Math.max(1, ...degrees.values());
  const cy = globalThis.cytoscape({
    container,
    elements: [
      ...data.nodes.map(n => ({data: {id: n.node_id, label: n.name,
        size:number('--graph-min') + (number('--graph-max') - number('--graph-min')) * Math.max(0,(degrees.get(n.node_id) - 1)) / Math.max(1,maxDegree - 1)}, classes: n.node_id === data.node.node_id ? 'focus' : ''})),
      ...data.edges.map(e => ({data: {id: `edge:${e.edge_id}`, source: e.src, target: e.dst, label: e.type}, classes: ['superseded','rejected'].includes(e.status) ? 'historical' : ''})),
    ],
    style: [
      {selector: 'node, edge', style: {'label':'data(label)', 'font-family':color('--font-sans'), 'font-size':number('--fs-xs'), 'color':color('--ink-2'), 'text-background-color':color('--surface'), 'text-background-opacity':number('--graph-label-opacity'), 'text-background-padding':3, 'transition-property':'opacity', 'transition-duration':window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : number('--dur-graph')}},
      {selector: 'node', style: {'background-color': color('--surface'), 'border-color': color('--ink-3'), 'border-width': 1.5, 'text-valign': 'bottom', 'text-margin-y': number('--graph-label-gap'), 'text-wrap': 'wrap', 'text-max-width': 120, 'width':'data(size)', 'height':'data(size)'}},
      {selector: 'node.focus', style: {'background-color': color('--accent'), 'border-color':color('--accent'), 'width': number('--graph-center'), 'height': number('--graph-center')}},
      {selector: 'edge', style: {'width': 1, 'line-color': color('--line-strong'), 'line-opacity':number('--graph-edge-opacity'), 'target-arrow-color': color('--line-strong'), 'target-arrow-shape': 'triangle', 'target-arrow-width':number('--graph-arrow'), 'curve-style': 'bezier', 'text-rotation': 'autorotate'}},
      {selector: '.historical', style: {'line-style': 'dashed', 'line-dash-pattern':[4,4]}},
      {selector: '.dim', style: {'opacity': number('--graph-dim-opacity')}},
      {selector: ':selected', style: {'border-color': color('--accent')}},
    ],
    layout: {name: 'fcose', quality: 'default', animate: false, padding: 45, nodeDimensionsIncludeLabels: true},
    minZoom: 0.15, maxZoom: 1,
  });
  cy.on('mouseover', 'node', event => {
    cy.elements().addClass('dim');
    event.target.closedNeighborhood().removeClass('dim');
  });
  cy.on('mouseout', 'node', () => cy.elements().removeClass('dim'));
  cy.on('tap', 'node', event => { location.hash = `#/entity/${encodeURIComponent(event.target.id())}`; });
  const fit = () => { cy.fit(undefined, 45); cy.center(); };
  fit();
  const button = document.querySelector('[data-fit]');
  button?.addEventListener('click', fit);
  const resize = new ResizeObserver(() => { cy.resize(); fit(); });
  resize.observe(container);
  return () => { resize.disconnect(); button?.removeEventListener('click', fit); cy.destroy(); };
}
