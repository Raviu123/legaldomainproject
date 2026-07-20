'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { GraphData, GraphNode, GraphRelationship } from '../lib/types';
import { ZoomIn, ZoomOut, RefreshCw, Info, Filter, MousePointer } from 'lucide-react';

interface GraphExplorerProps {
  graphData: GraphData;
  selectedLawId?: string;
  onFetchGraph?: (lawId: string, limit: number) => Promise<void>;
}

interface SimNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

export default function GraphExplorer({ graphData, selectedLawId = '', onFetchGraph }: GraphExplorerProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [nodes, setNodes] = useState<SimNode[]>([]);
  const [edges, setEdges] = useState<GraphRelationship[]>([]);
  const [nodeLimit, setNodeLimit] = useState<number>(100);
  const [isFetching, setIsFetching] = useState<boolean>(false);
  
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
    Chapter: true,
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

  // Precompute settled node positions in a neat concentric hierarchical layout
  useEffect(() => {
    if (graphData.nodes.length === 0) {
      setNodes([]);
      setEdges([]);
      setSelectedNode(null);
      return;
    }

    const centerX = width / 2;
    const centerY = height / 2;

    // Categorize nodes by structural hierarchical levels
    const lawNodes = graphData.nodes.filter((n) => n.label === 'Law');
    const chapterNodes = graphData.nodes.filter((n) => n.label === 'Chapter');
    const articleNodes = graphData.nodes.filter((n) => n.label === 'Article');
    const otherNodes = graphData.nodes.filter(
      (n) => n.label !== 'Law' && n.label !== 'Chapter' && n.label !== 'Article'
    );

    const nodeMap = new Map<string, SimNode>();

    // Level 0: Law (Center)
    lawNodes.forEach((node, idx) => {
      const angle = (idx / Math.max(lawNodes.length, 1)) * 2 * Math.PI;
      const radius = lawNodes.length > 1 ? 35 : 0;
      const sn: SimNode = {
        ...node,
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * radius,
        vx: 0,
        vy: 0,
      };
      nodeMap.set(node.id, sn);
    });

    // Level 1: Chapters (Inner Ring - 130px)
    chapterNodes.forEach((node, idx) => {
      const angle = (idx / Math.max(chapterNodes.length, 1)) * 2 * Math.PI - Math.PI / 2;
      const radius = 135;
      const sn: SimNode = {
        ...node,
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * radius,
        vx: 0,
        vy: 0,
      };
      nodeMap.set(node.id, sn);
    });

    // Level 2: Articles (Middle Ring - 230px with subtle radial staggering)
    articleNodes.forEach((node, idx) => {
      const angle = (idx / Math.max(articleNodes.length, 1)) * 2 * Math.PI - Math.PI / 2;
      const radius = 225 + (idx % 2 === 0 ? -12 : 12);
      const sn: SimNode = {
        ...node,
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * radius,
        vx: 0,
        vy: 0,
      };
      nodeMap.set(node.id, sn);
    });

    // Level 3: Concepts & Definitions (Outer Ring - 310px)
    otherNodes.forEach((node, idx) => {
      const angle = (idx / Math.max(otherNodes.length, 1)) * 2 * Math.PI - Math.PI / 2;
      const radius = 310 + (idx % 2 === 0 ? -15 : 15);
      const sn: SimNode = {
        ...node,
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * radius,
        vx: 0,
        vy: 0,
      };
      nodeMap.set(node.id, sn);
    });

    const simNodes = Array.from(nodeMap.values());

    // Relaxation passes to eliminate overlapping nodes
    for (let step = 0; step < 40; step++) {
      for (let i = 0; i < simNodes.length; i++) {
        const n1 = simNodes[i];
        if (n1.label === 'Law') continue; // keep center stationary
        for (let j = i + 1; j < simNodes.length; j++) {
          const n2 = simNodes[j];
          if (n2.label === 'Law') continue;
          const dx = n2.x - n1.x;
          const dy = n2.y - n1.y;
          const distSq = dx * dx + dy * dy + 1;
          const dist = Math.sqrt(distSq);
          const minAllowedDist = 42;
          if (dist < minAllowedDist) {
            const push = (minAllowedDist - dist) * 0.2;
            const fx = (dx / dist) * push;
            const fy = (dy / dist) * push;
            n1.x -= fx;
            n1.y -= fy;
            n2.x += fx;
            n2.y += fy;
          }
        }
      }

      // Constrain boundaries
      simNodes.forEach((node) => {
        node.x = Math.max(45, Math.min(width - 45, node.x));
        node.y = Math.max(45, Math.min(height - 45, node.y));
      });
    }

    setNodes(simNodes);
    setEdges(graphData.edges);
    setSelectedNode(null);
  }, [graphData]);


  // Handle limit change
  const handleLimitChange = async (newLimit: number) => {
    setNodeLimit(newLimit);
    if (onFetchGraph) {
      setIsFetching(true);
      try {
        await onFetchGraph(selectedLawId, newLimit);
      } catch (_) {
      } finally {
        setIsFetching(false);
      }
    }
  };

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
    // Trigger re-layout
    setNodes((prev) => [...prev]);
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

  // Determine active highlighted nodes & edges on hover
  const { highlightedNodeIds, activeEdgesMap } = useMemo(() => {
    const nodeSet = new Set<string>();
    const activeEdges = new Set<string>();

    const activeId = hoveredNode || selectedNode?.id;
    if (!activeId) return { highlightedNodeIds: nodeSet, activeEdgesMap: activeEdges };

    nodeSet.add(activeId);
    visibleEdges.forEach((edge) => {
      if (edge.source === activeId || edge.target === activeId) {
        nodeSet.add(edge.source);
        nodeSet.add(edge.target);
        activeEdges.add(`${edge.source}___${edge.target}`);
      }
    });

    return { highlightedNodeIds: nodeSet, activeEdgesMap: activeEdges };
  }, [visibleEdges, hoveredNode, selectedNode]);

  return (
    <div className="flex h-full flex-1 overflow-hidden">
      {/* Interactive Graph Area */}
      <div className="relative flex flex-1 flex-col overflow-hidden bg-zinc-50 dark:bg-zinc-950">
        
        {/* Controls Overlay */}
        <div className="absolute left-4 top-4 z-10 flex items-center gap-2 rounded-xl border border-zinc-200 bg-white/90 p-2 shadow-sm backdrop-blur-md dark:border-zinc-800 dark:bg-zinc-900/90">
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
            <RefreshCw className={`h-4.5 w-4.5 ${isFetching ? 'animate-spin' : ''}`} />
          </button>

          <div className="h-4 w-[1px] bg-zinc-200 dark:bg-zinc-800 mx-1" />

          {/* Node Limit Selector */}
          <div className="flex items-center gap-1.5 text-xs text-zinc-600 dark:text-zinc-400">
            <span className="font-medium">Limit:</span>
            <select
              value={nodeLimit}
              onChange={(e) => handleLimitChange(Number(e.target.value))}
              disabled={isFetching}
              className="rounded-lg border border-zinc-300 bg-white px-2 py-1 text-xs font-semibold text-zinc-900 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
            >
              <option value={50} className="bg-white text-zinc-900 dark:bg-zinc-900 dark:text-zinc-100">50 Edges</option>
              <option value={100} className="bg-white text-zinc-900 dark:bg-zinc-900 dark:text-zinc-100">100 Edges</option>
              <option value={200} className="bg-white text-zinc-900 dark:bg-zinc-900 dark:text-zinc-100">200 Edges</option>
              <option value={300} className="bg-white text-zinc-900 dark:bg-zinc-900 dark:text-zinc-100">300 Edges</option>
            </select>
          </div>
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
              <path d="M 0 0 L 10 5 L 0 10 z" className="fill-zinc-400 dark:fill-zinc-500" />
            </marker>
            <marker
              id="arrow-active"
              viewBox="0 0 10 10"
              refX="24"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" className="fill-indigo-600 dark:fill-indigo-400" />
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

                const isHoveredEdge = activeEdgesMap.has(`${edge.source}___${edge.target}`);
                const isAnyNodeHovered = Boolean(hoveredNode || selectedNode?.id);

                let lineStyle = 'stroke-zinc-400/80 dark:stroke-zinc-500/80 stroke-[1.5px]';
                if (isAnyNodeHovered) {
                  if (isHoveredEdge) {
                    lineStyle = 'stroke-indigo-600 dark:stroke-indigo-400 stroke-[2.5px] opacity-100';
                  } else {
                    lineStyle = 'stroke-zinc-300/20 dark:stroke-zinc-800/20 stroke-[1px] opacity-15';
                  }
                }

                return (
                  <g key={idx} className="transition-all duration-200">
                    <line
                      x1={srcNode.x}
                      y1={srcNode.y}
                      x2={tgtNode.x}
                      y2={tgtNode.y}
                      markerEnd={isHoveredEdge ? 'url(#arrow-active)' : 'url(#arrow)'}
                      className={`transition-all ${lineStyle}`}
                    />
                    {/* Edge label displayed clearly when edge is active */}
                    {(isHoveredEdge || (hoveredNode === edge.source || hoveredNode === edge.target)) && (
                      <text
                        x={(srcNode.x + tgtNode.x) / 2}
                        y={(srcNode.y + tgtNode.y) / 2 - 4}
                        textAnchor="middle"
                        className="fill-indigo-600 dark:fill-indigo-400 font-bold text-[9px] select-none"
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
                const isAnyNodeHovered = Boolean(hoveredNode || selectedNode?.id);
                const isHighlightedNode = !isAnyNodeHovered || highlightedNodeIds.has(node.id);
                const colorClasses = getNodeColor(node.label, isSelected);

                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.x}, ${node.y})`}
                    className={`cursor-pointer transition-opacity duration-200 ${
                      isHighlightedNode ? 'opacity-100' : 'opacity-20'
                    }`}
                    onMouseDown={(e) => handleNodeMouseDown(e, node)}
                    onMouseEnter={() => setHoveredNode(node.id)}
                    onMouseLeave={() => setHoveredNode(null)}
                  >
                    {/* Node circle */}
                    <circle
                      r={node.label === 'Law' ? 20 : node.label === 'Chapter' ? 15 : 11}
                      className={`${colorClasses} stroke-2 transition-all ${
                        isSelected ? 'ring-4 ring-indigo-500/30' : ''
                      }`}
                    />
                    
                    {/* Node label text */}
                    <text
                      dy="24"
                      textAnchor="middle"
                      className={`select-none text-[10px] font-semibold transition-all ${
                        isHighlightedNode 
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
