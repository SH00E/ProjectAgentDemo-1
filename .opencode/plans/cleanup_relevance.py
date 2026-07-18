import re

path = 'repair_agent/ui/static/dashboard.html'
with open(path, encoding='utf-8') as f:
    text = f.read()

# Remove Hub node block and simplify force simulation
text = text.replace("""            const nodes = data.nodes.map(n => ({...n}));
            const links = data.links.map(l => ({...l}));

            const hubId = "__hub__";
            nodes.push({ id: hubId, type: "Hub", label: "\u88c5\u5907\u77e5\u8bc6\u56fe\u8c31", group: "hub" });
            const qaChapters = nodes.filter(n => n.type === "QAChapter");
            const topAircraft = nodes.filter(n => n.type === "Aircraft").slice(0, 5);
            const topMfgs = nodes.filter(n => n.type === "Manufacturer").slice(0, 3);
            for (const ch of qaChapters) {
                links.push({ source: hubId, target: ch.id, type: "HUB_QA", weight: 1 });
            }
            for (const a of topAircraft) {
                links.push({ source: hubId, target: a.id, type: "HUB_AVIATION", weight: 1 });
            }
            for (const m of topMfgs) {
                links.push({ source: hubId, target: m.id, type: "HUB_AVIATION", weight: 1 });
            }

            const sim = d3.forceSimulation(nodes)
                .force('link', d3.forceLink(links).id(d => d.id).distance(d => {
                    if (d.type === 'BELONGS_TO') return 30;
                    if (d.type === 'HUB_QA' || d.type === 'HUB_AVIATION') return 120;
                    if (d.type === 'MANUFACTURED_BY') return 60;
                    return 80;
                }).strength(d => {
                    if (d.type === 'BELONGS_TO') return 0.8;
                    if (d.type === 'HUB_QA' || d.type === 'HUB_AVIATION') return 0.1;
                    return 0.2;
                }))
                .force('charge', d3.forceManyBody().strength(-180))
                .force('center', d3.forceCenter(W/2, H/2))
                .force('collision', d3.forceCollide(18));

            const link = g.append('g').selectAll('line')
                .data(links).join('line')
                .attr('stroke', '#334155')
                .attr('stroke-width', d => d.type === 'HUB_QA' || d.type === 'HUB_AVIATION' ? 0.8 : d.type === 'BELONGS_TO' ? 1 : d.weight ? Math.min(Math.sqrt(d.weight)*0.5, 4) : 1.5)
                .attr('stroke-dasharray', d => d.type === 'HUB_QA' || d.type === 'HUB_AVIATION' ? '4,4' : null)
                .attr('stroke-opacity', d => d.type === 'HUB_QA' || d.type === 'HUB_AVIATION' ? 0.3 : 0.6);

            const node = g.append('g').selectAll('g')
                .data(nodes).join('g')
                .attr('cursor', 'pointer')
                .call(d3.drag()
                    .on('start', (event, d) => { if (!event.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
                    .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
                    .on('end', (event, d) => { if (!event.active) sim.alphaTarget(0); d.fx = null; d.fy = null; })
                );

            node.append('circle')
                .attr('r', d => d.type === 'Hub' ? 14 : d.type === 'QAChapter' ? 12 : d.type === 'QAPair' ? 5 : d.type === 'Aircraft' ? 10 : 7)
                .attr('fill', d => d.type === 'Hub' ? '#e2e8f0' : typeColors[d.type] || '#94a3b8')
                .attr('stroke', d => d.type === 'Hub' ? '#94a3b8' : '#1e293b')
                .attr('stroke-width', d => d.type === 'Hub' ? 3 : 2)
                .attr('stroke-dasharray', d => d.type === 'Hub' ? '3,2' : null);

            node.append('text')
                .text(d => d.type === 'Hub' ? d.label : d.label.length > 18 ? d.label.slice(0, 18) + '...' : d.label)
                .attr('x', d => d.type === 'Hub' ? 18 : d.type === 'QAChapter' ? 16 : 10)
                .attr('y', d => d.type === 'Hub' ? 5 : 4)
                .attr('font-size', d => d.type === 'Hub' ? 12 : d.type === 'QAChapter' ? 10 : 8)
                .attr('fill', d => d.type === 'Hub' ? '#94a3b8' : '#cbd5e1')
                .attr('font-weight', d => d.type === 'Hub' ? 'bold' : 'normal')
                .attr('pointer-events', 'none');""",

"""            const nodes = data.nodes.map(n => ({...n}));
            const links = data.links.map(l => ({...l}));

            const sim = d3.forceSimulation(nodes)
                .force('link', d3.forceLink(links).id(d => d.id).distance(d => {
                    if (d.type === 'BELONGS_TO') return 40;
                    if (d.type === 'RELATED_TO') return 60;
                    if (d.type === 'MANUFACTURED_BY') return 60;
                    return 80;
                }).strength(d => {
                    if (d.type === 'BELONGS_TO') return 0.8;
                    if (d.type === 'RELATED_TO') return 0.3;
                    return 0.2;
                }))
                .force('charge', d3.forceManyBody().strength(-150))
                .force('center', d3.forceCenter(W/2, H/2))
                .force('collision', d3.forceCollide(18));

            const link = g.append('g').selectAll('line')
                .data(links).join('line')
                .attr('stroke', '#334155')
                .attr('stroke-width', d => d.type === 'RELATED_TO' ? 1.2 : d.type === 'BELONGS_TO' ? 1 : d.weight ? Math.min(Math.sqrt(d.weight)*0.5, 4) : 1.5)
                .attr('stroke-dasharray', d => d.type === 'RELATED_TO' ? '4,4' : null)
                .attr('stroke-opacity', d => d.type === 'RELATED_TO' ? 0.4 : 0.6);

            const node = g.append('g').selectAll('g')
                .data(nodes).join('g')
                .attr('cursor', 'pointer')
                .call(d3.drag()
                    .on('start', (event, d) => { if (!event.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
                    .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
                    .on('end', (event, d) => { if (!event.active) sim.alphaTarget(0); d.fx = null; d.fy = null; })
                );

            node.append('circle')
                .attr('r', d => d.type === 'QAChapter' ? 12 : d.type === 'QAPair' ? 6 : d.type === 'Aircraft' ? 10 : 7)
                .attr('fill', d => typeColors[d.type] || '#94a3b8')
                .attr('stroke', '#1e293b')
                .attr('stroke-width', 2);

            node.append('text')
                .text(d => d.label.length > 18 ? d.label.slice(0, 18) + '...' : d.label)
                .attr('x', d => d.type === 'QAChapter' ? 16 : 10)
                .attr('y', 4)
                .attr('font-size', d => d.type === 'QAChapter' ? 10 : 8)
                .attr('fill', '#cbd5e1')
                .attr('pointer-events', 'none');""")

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Dashboard cleaned - Hub removed, RELATED_TO added')
