'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { GraphData, GraphNode, GraphRelationship } from '../lib/types';
import { ZoomIn, ZoomOut, RefreshCw, Info, Filter, MousePointer } from 'lucide-react';

interface GraphExplorerProps {
  graphData: GraphData;
}

interface SimNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

export default function GraphExplorer({ graphData }: GraphExplorerProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [nodes, setNodes] = useState<SimNode[]>([]);
  const [edges, setEdges] = useState<GraphRelationship[]>([]);
  
  // Viewport state
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });

  // Interaction state
  const [selectedNode, setSelectedNode] = useState<SimNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [draggedNodeId, setDraggedNodeId] = useState<string | null>(null);

  // Filters state
  const [visibleLabels, setVisibleLabels] = useState<Record<string, boolean>>({
    Law: true,
    Article: true,
    Concept: true,
    Definition: true,
  });

  const width = 800;
  const height = 550;

  // Color mapping based on node type/label
  const getNodeColor = (label: string, isHighlighted: boolean) => {
    switch (label) {
      case 'Law':
        return isHighlighted ? 'fill-indigo-600 stroke-indigo-300' : 'fill-indigo-500 stroke-indigo-200';
      case 'Article':
        return isHighlighted ? 'fill-violet-600 stroke-violet-300' : 'fill-violet-500 stroke-violet-200';
      case 'Concept':
        return isHighlighted ? 'fill-emerald-600 stroke-emerald-300' : 'fill-emerald-500 stroke-emerald-200';
      case 'Definition':
        return isHighlighted ? 'fill-amber-600 stroke-amber-300' : 'fill-amber-500 stroke-amber-200';
      default:
        return isHighlighted ? 'fill-zinc-600 stroke-zinc-300' : 'fill-zinc-500 stroke-zinc-200';
    }
  };

  // Re-initialize nodes on graphData changes
  useEffect(() => {
    const initializedNodes = graphData.nodes.map((node, index) => {
      // Position nodes in a neat circle initially
      const angle = (index / graphData.nodes.length) * 2 * Math.PI;
      const radius = 150 + Math.random() * 50;
      return {
        ...node,
        x: width / 2 + Math.cos(angle) * radius,
        y: height / 2 + Math.sin(angle) * radius,
        vx: 0,
        vy: 0,
      };
    });
    setNodes(initializedNodes);
    setEdges(graphData.edges);
  }, [graphData]);

  // Run the force-directed simulation
  useEffect(() => {
    if (nodes.length === 0) return;

    let animFrame: number;
    const forceStrength = 0.05;
    const linkDistance = 120;
    const repulsionStrength = 800;
    const centerGravity = 0.02;

    const tick = () => {
      setNodes((prevNodes) => {
        // Create working copies
        const workingNodes = prevNodes.map((n) => ({ ...n }));
        const nodeMap = new Map(workingNodes.map((n) => [n.id, n]));

        // 1. Repulsion between all nodes (charge force)
        for (let i = 0; i < workingNodes.length; i++) {
          const n1 = workingNodes[i];
          for (let j = i + 1; j < workingNodes.length; j++) {
            const n2 = workingNodes[j];
            const dx = n2.x - n1.x;
            const dy = n2.y - n1.y;
            const distSq = dx * dx + dy * dy + 1; // avoid divide by zero
            const dist = Math.sqrt(distSq);

            if (dist < 300) {
              const force = repulsionStrength / distSq;
              const fx = (dx / dist) * force;
              const fy = (dy / dist) * force;

              // Repel each other
              if (n1.id !== draggedNodeId) {
                n1.vx -= fx;
                n1.vy -= fy;
              }
              if (n2.id !== draggedNodeId) {
                n2.vx += fx;
                n2.vy += fy;
              }
            }
          }
        }

        // 2. Link force (springs between connected nodes)
        edges.forEach((edge) => {
          const sourceNode = nodeMap.get(edge.source);
          const targetNode = nodeMap.get(edge.target);

          if (sourceNode && targetNode) {
            const dx = targetNode.x - sourceNode.x;
            const dy = targetNode.y - sourceNode.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const force = (dist - linkDistance) * forceStrength;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;

            if (sourceNode.id !== draggedNodeId) {
              sourceNode.vx += fx;
              sourceNode.vy += fy;
            }
            if (targetNode.id !== draggedNodeId) {
              targetNode.vx -= fx;
              targetNode.vy -= fy;
            }
          }
        });

        // 3. Center gravity (pull towards screen center)
        workingNodes.forEach((node) => {
          if (node.id === draggedNodeId) return;
          const dx = width / 2 - node.x;
          const dy = height / 2 - node.y;
          node.vx += dx * centerGravity;
          node.vy += dy * centerGravity;
        });

        // 4. Update positions with damping
        workingNodes.forEach((node) => {
          if (node.id === draggedNodeId) return;
          node.vx *= 0.85; // friction
          node.vy *= 0.85;
          node.x += node.vx;
          node.y += node.vy;

          // Boundary constraints
          node.x = Math.max(40, Math.min(width - 40, node.x));
          node.y = Math.max(40, Math.min(height - 40, node.y));
        });

        return workingNodes;
      });

      animFrame = requestAnimationFrame(tick);
    };

    animFrame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animFrame);
  }, [edges, draggedNodeId, nodes.length]);

  // Handle Dragging
  const handleNodeMouseDown = (e: React.MouseEvent, node: SimNode) => {
    e.stopPropagation();
    setDraggedNodeId(node.id);
    setSelectedNode(node);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (draggedNodeId && svgRef.current) {
      // Calculate coordinates relative to SVG scale and pan
      const rect = svgRef.current.getBoundingClientRect();
      const clientX = e.clientX - rect.left;
      const clientY = e.clientY - rect.top;
      
      const svgX = (clientX - pan.x) / zoom;
      const svgY = (clientY - pan.y) / zoom;

      setNodes((prevNodes) =>
        prevNodes.map((n) =>
          n.id === draggedNodeId ? { ...n, x: svgX, y: svgY, vx: 0, vy: 0 } : n
        )
      );
    } else if (isPanning) {
      const dx = e.clientX - panStart.x;
      const dy = e.clientY - panStart.y;
      setPan({ x: panStart.x + dx, y: panStart.y + dy });
    }
  };

  const handleMouseUp = () => {
    setDraggedNodeId(null);
    setIsPanning(false);
  };

  // Handle SVG canvas panning
  const handleCanvasMouseDown = (e: React.MouseEvent) => {
    setIsPanning(true);
    setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  // Zoom Helpers
  const handleZoomIn = () => setZoom((z) => Math.min(z + 0.15, 3));
  const handleZoomOut = () => setZoom((z) => Math.max(z - 0.15, 0.4));
  const handleResetLayout = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    // Re-jitter nodes
    setNodes((prevNodes) =>
      prevNodes.map((node, index) => {
        const angle = (index / prevNodes.length) * 2 * Math.PI;
        return {
          ...node,
          x: width / 2 + Math.cos(angle) * 150,
          y: height / 2 + Math.sin(angle) * 150,
          vx: 0,
          vy: 0,
        };
      })
    );
  };

  // Filter elements to render
  const visibleNodes = useMemo(() => {
    return nodes.filter((node) => visibleLabels[node.label] !== false);
  }, [nodes, visibleLabels]);

  const visibleNodesMap = useMemo(() => {
    return new Map(visibleNodes.map((n) => [n.id, n]));
  }, [visibleNodes]);

  const visibleEdges = useMemo(() => {
    return edges.filter(
      (edge) => visibleNodesMap.has(edge.source) && visibleNodesMap.has(edge.target)
    );
  }, [edges, visibleNodesMap]);

  // Determine highlight list (active node neighbors)
  const highlightedNodeIds = useMemo(() => {
    const set = new Set<string>();
    const activeId = hoveredNode || selectedNode?.id;
    if (!activeId) return set;

    set.add(activeId);
    visibleEdges.forEach((edge) => {
      if (edge.source === activeId) set.add(edge.target);
      if (edge.target === activeId) set.add(edge.source);
    });
    return set;
  }, [visibleEdges, hoveredNode, selectedNode]);

  return (
    <div className="flex h-full flex-1 overflow-hidden">
      {/* Interactive Graph Area */}
      <div className="relative flex flex-1 flex-col overflow-hidden bg-zinc-50 dark:bg-zinc-950">
        
        {/* Controls Overlay */}
        <div className="absolute left-4 top-4 z-10 flex gap-2 rounded-xl border border-zinc-200 bg-white/90 p-2 shadow-sm backdrop-blur-md dark:border-zinc-800 dark:bg-zinc-900/90">
          <button
            onClick={handleZoomIn}
            title="Zoom In"
            className="flex h-8 w-8 items-center justify-center rounded-lg text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
          >
            <ZoomIn className="h-4.5 w-4.5" />
          </button>
          <button
            onClick={handleZoomOut}
            title="Zoom Out"
            className="flex h-8 w-8 items-center justify-center rounded-lg text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
          >
            <ZoomOut className="h-4.5 w-4.5" />
          </button>
          <button
            onClick={handleResetLayout}
            title="Reset Graph Layout"
            className="flex h-8 w-8 items-center justify-center rounded-lg text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
          >
            <RefreshCw className="h-4.5 w-4.5" />
          </button>
        </div>

        {/* Filter Toolbar overlay */}
        <div className="absolute right-4 top-4 z-10 flex flex-col gap-2 rounded-xl border border-zinc-200 bg-white/90 p-3 shadow-sm backdrop-blur-md dark:border-zinc-800 dark:bg-zinc-900/90">
          <div className="flex items-center gap-1.5 text-xs font-bold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
            <Filter className="h-3.5 w-3.5" />
            <span>Visible Nodes</span>
          </div>
          <div className="mt-2 space-y-1.5 text-xs">
            {Object.keys(visibleLabels).map((lbl) => (
              <label key={lbl} className="flex items-center gap-2 cursor-pointer text-zinc-700 dark:text-zinc-300">
                <input
                  type="checkbox"
                  checked={visibleLabels[lbl]}
                  onChange={() =>
                    setVisibleLabels((prev) => ({ ...prev, [lbl]: !prev[lbl] }))
                  }
                  className="rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span>{lbl}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Graph Canvas */}
        <svg
          ref={svgRef}
          className="h-full w-full cursor-grab active:cursor-grabbing outline-none"
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onMouseDown={handleCanvasMouseDown}
        >
          {/* Arrow markers for edges */}
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="22"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" className="fill-zinc-300 dark:fill-zinc-700" />
            </marker>
          </defs>

          {/* Group containing all elements to scale and pan */}
          <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
            
            {/* Draw Relationships/Edges */}
            <g>
              {visibleEdges.map((edge, idx) => {
                const srcNode = visibleNodesMap.get(edge.source);
                const tgtNode = visibleNodesMap.get(edge.target);
                if (!srcNode || !tgtNode) return null;

                const isHighlighted = highlightedNodeIds.size === 0 || 
                  (highlightedNodeIds.has(edge.source) && highlightedNodeIds.has(edge.target));

                return (
                  <g key={idx} className="transition-opacity duration-200">
                    <line
                      x1={srcNode.x}
                      y1={srcNode.y}
                      x2={tgtNode.x}
                      y2={tgtNode.y}
                      markerEnd="url(#arrow)"
                      className={`stroke-2 transition-all ${
                        isHighlighted 
                          ? 'stroke-zinc-300 dark:stroke-zinc-700' 
                          : 'stroke-zinc-200/30 dark:stroke-zinc-800/10'
                      }`}
                    />
                    {/* Optional edge label on hover */}
                    {isHighlighted && (hoveredNode === edge.source || hoveredNode === edge.target) && (
                      <text
                        x={(srcNode.x + tgtNode.x) / 2}
                        y={(srcNode.y + tgtNode.y) / 2 - 4}
                        textAnchor="middle"
                        className="fill-zinc-400 dark:fill-zinc-500 font-medium text-[8px] select-none"
                      >
                        {edge.type}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>

            {/* Draw Nodes */}
            <g>
              {visibleNodes.map((node) => {
                const isSelected = selectedNode?.id === node.id;
                const isHighlighted = highlightedNodeIds.size === 0 || highlightedNodeIds.has(node.id);
                const colorClasses = getNodeColor(node.label, isSelected);

                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.x}, ${node.y})`}
                    className="cursor-pointer transition-opacity duration-200"
                    onMouseDown={(e) => handleNodeMouseDown(e, node)}
                    onMouseEnter={() => setHoveredNode(node.id)}
                    onMouseLeave={() => setHoveredNode(null)}
                  >
                    {/* Node circle */}
                    <circle
                      r={node.label === 'Law' ? 18 : 12}
                      className={`${colorClasses} stroke-2 transition-all ${
                        isHighlighted ? 'opacity-100' : 'opacity-20'
                      } ${isSelected ? 'ring-4 ring-indigo-500/20' : ''}`}
                    />
                    
                    {/* Node label text */}
                    <text
                      dy="24"
                      textAnchor="middle"
                      className={`select-none text-[10px] font-semibold transition-all ${
                        isHighlighted 
                          ? 'fill-zinc-800 dark:fill-zinc-200' 
                          : 'fill-zinc-400/20 dark:fill-zinc-600/10'
                      }`}
                    >
                      {node.properties.name || node.properties.title || node.id}
                    </text>

                    {/* Small badge representing node type */}
                    <text
                      dy="-20"
                      textAnchor="middle"
                      className="select-none text-[8px] font-medium fill-zinc-400 opacity-0 group-hover:opacity-100"
                    >
                      {node.label}
                    </text>
                  </g>
                );
              })}
            </g>
          </g>
        </svg>

        {/* Tip footer overlay */}
        <div className="absolute bottom-4 left-4 text-[10px] text-zinc-400 flex items-center gap-1.5 pointer-events-none">
          <MousePointer className="h-3.5 w-3.5" />
          <span>Drag nodes to organize. Drag background to pan. Scroll/Pinch to zoom.</span>
        </div>
      </div>

      {/* Graph Inspector Panel (Right side) */}
      <div className="w-80 border-l border-zinc-200 bg-white p-6 overflow-y-auto dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 border-b border-zinc-100 pb-3 dark:border-zinc-800">
          <Info className="h-4 w-4 text-indigo-500" />
          Graph Node Inspector
        </h3>

        {selectedNode ? (
          <div className="mt-5 space-y-4">
            <div>
              <span className="inline-block rounded-md bg-zinc-100 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                {selectedNode.label}
              </span>
              <h4 className="mt-2 text-base font-bold text-zinc-900 dark:text-white">
                {selectedNode.properties.name || selectedNode.properties.title || selectedNode.id}
              </h4>
            </div>

            {/* Properties List */}
            <div className="space-y-3 pt-3 border-t border-zinc-100 dark:border-zinc-800">
              <span className="block text-[10px] font-bold uppercase tracking-wider text-zinc-400">Node Properties</span>
              
              <div className="space-y-2.5 text-xs">
                <div>
                  <span className="block text-[10px] text-zinc-400">Stable Node ID</span>
                  <code className="mt-0.5 block rounded bg-zinc-50 p-1.5 font-mono text-[10px] text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">
                    {selectedNode.id}
                  </code>
                </div>

                {Object.entries(selectedNode.properties).map(([key, val]) => {
                  if (key === 'name' || key === 'title') return null; // already shown
                  return (
                    <div key={key}>
                      <span className="block text-[10px] text-zinc-400 capitalize">{key}</span>
                      <span className="mt-0.5 block text-zinc-800 dark:text-zinc-200 font-medium">
                        {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Direct Connections summary */}
            <div className="space-y-2 pt-3 border-t border-zinc-100 dark:border-zinc-800">
              <span className="block text-[10px] font-bold uppercase tracking-wider text-zinc-400">Direct Connections</span>
              <ul className="space-y-1.5">
                {edges
                  .filter((e) => e.source === selectedNode.id || e.target === selectedNode.id)
                  .map((edge, idx) => {
                    const otherId = edge.source === selectedNode.id ? edge.target : edge.source;
                    const direction = edge.source === selectedNode.id ? 'outgoing' : 'incoming';
                    return (
                      <li key={idx} className="flex items-center justify-between rounded-lg bg-zinc-50/50 p-2 text-xs dark:bg-zinc-900/30">
                        <span className="font-mono text-[10px] text-zinc-500 truncate max-w-[140px]">{otherId}</span>
                        <span className="rounded bg-zinc-200/50 px-1.5 py-0.5 text-[9px] font-medium text-zinc-600 dark:bg-zinc-850 dark:text-zinc-400">
                          {edge.type} ({direction})
                        </span>
                      </li>
                    );
                  })}
              </ul>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-20 text-center text-zinc-400">
            <MousePointer className="h-8 w-8 text-zinc-300 animate-pulse" />
            <p className="mt-4 text-xs font-semibold text-zinc-500">No node selected</p>
            <p className="mt-1 max-w-[160px] text-[10px] leading-relaxed">Click any node in the graph to view its metadata and relationships.</p>
          </div>
        )}
      </div>
    </div>
  );
}
