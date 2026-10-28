// Render only the supplied local neighborhood. Destroy on navigation/privacy change.
export function renderGraph(data) {
  const container = document.getElementById('graph');
  if (!container || !globalThis.cytoscape) return () => {};
  const colors = getComputedStyle(document.documentElement);
  const color = name => colors.getPropertyValue(name).trim();
  const cy = globalThis.cytoscape({
    container,
    elements: [
      ...data.nodes.map(n => ({data: {id: n.node_id, label: n.name}, classes: n.node_id === data.node.node_id ? 'focus' : ''})),
      ...data.edges.map(e => ({data: {id: `edge:${e.edge_id}`, source: e.src, target: e.dst, label: e.type}, classes: ['superseded','rejected'].includes(e.status) ? 'historical' : ''})),
    ],
    style: [
      {selector: 'node', style: {'background-color': color('--surface'), 'border-color': color('--accent'), 'border-width': 2, 'color': color('--ink'), 'label': 'data(label)', 'font-size': 13, 'text-valign': 'bottom', 'text-margin-y': 10, 'text-wrap': 'wrap', 'text-max-width': 120, 'width': 28, 'height': 28}},
      {selector: 'node.focus', style: {'background-color': color('--accent'), 'width': 42, 'height': 42, 'underlay-color': color('--accent'), 'underlay-opacity': 0.16, 'underlay-padding': 12}},
      {selector: 'edge', style: {'width': 1.5, 'line-color': color('--muted'), 'target-arrow-color': color('--muted'), 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', 'label': 'data(label)', 'font-size': 10, 'color': color('--muted'), 'text-background-color': color('--surface'), 'text-background-opacity': 1, 'text-background-padding': 3, 'text-rotation': 'autorotate'}},
      {selector: '.historical', style: {'line-style': 'dashed', 'opacity': 0.55}},
      {selector: '.dim', style: {'opacity': 0.18}},
      {selector: ':selected', style: {'border-width': 4, 'border-color': color('--accent')}},
    ],
    layout: {name: 'fcose', quality: 'default', animate: false, padding: 45, nodeDimensionsIncludeLabels: true},
    minZoom: 0.15, maxZoom: 1, wheelSensitivity: 0.3,
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
