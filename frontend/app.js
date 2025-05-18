document.addEventListener('DOMContentLoaded', () => {
    const graphContainer = document.getElementById('task-graph');
    const detailsContent = document.getElementById('details-content');
    const overallGoalDiv = document.getElementById('overall-goal');
    const API_URL = 'http://127.0.0.1:5000/api/task-graph';
    const POLLING_INTERVAL = 10000; // Poll every 10 seconds (10000 ms)
    const projectGoalInput = document.getElementById('project-goal-input');
    const startProjectButton = document.getElementById('start-project-button');
    const projectStatusMessage = document.getElementById('project-status-message');
    let contextFlowToggle; // Will be initialized in DOMContentLoaded

    if (projectGoalInput) {
        projectGoalInput.value = "Write me a detailed report about the recent U.S. trade tariffs and their effect on the global economy";
    }

    let allNodesData = {}; // To store full node details for click events
    let network = null; // Keep a reference to the network object
    let contextFlowEdges = new vis.DataSet();
    let pollingIntervalId = null; // To store the interval ID
    let showdownConverter = null; // For Markdown
    let showContextFlow = true; // Default to showing context flow lines

    // --- Color mapping for status ---
    const statusColors = {
        PENDING: '#CCCCCC', // Grey
        READY: '#A9A9A9',   // Dark Grey
        RUNNING: '#FFA500', // Orange
        PLAN_DONE: '#FFFF00', // Yellow
        AGGREGATING: '#FFD700', // Gold
        DONE: '#90EE90',    // Light Green
        FAILED: '#FF6347',  // Tomato Red
        NEEDS_REPLAN: '#FF4500' // OrangeRed
    };

    const nodeTypeStyles = {
        PLAN: { shape: 'box', label: 'Plan Node' },
        EXECUTE: { shape: 'ellipse', label: 'Execute Node' }
    };

    // Define edge styles for the legend
    const edgeLegendStyles = [
        { type: 'Dependency', color: '#3498DB', dashes: false, label: 'Dependency Link' }, // Solid blue
        { type: 'Hierarchy', color: '#ADADAD', dashes: true, label: 'Hierarchical Link (Parent-Child)' },
        { type: 'ContextFlow', color: '#FF69B4', dashes: [5,5], label: 'Context Flow Link' } // Use array for vis.js dash style
    ];

    function stopPolling() {
        if (pollingIntervalId !== null) {
            clearInterval(pollingIntervalId);
            pollingIntervalId = null;
            console.log("Polling stopped.");
            // projectStatusMessage.textContent = 'Polling paused (node selected).'; // Optional
        }
    }

    function startPolling() {
        if (pollingIntervalId === null) { // Only start if not already running
            // projectStatusMessage.textContent = ''; // Clear "paused" message or set to default
            console.log("Polling starting/resuming.");
            fetchAndDrawGraph(true); // Fetch immediately then start interval
            pollingIntervalId = setInterval(() => {
                fetchAndDrawGraph(true);
            }, POLLING_INTERVAL);
        }
    }

    async function fetchAndDrawGraph(isPollingUpdate = false) {
        try {
            const response = await fetch(API_URL);
            if (!response.ok) {
                console.error(`HTTP error! status: ${response.status}`);
                // Stop polling on significant error to avoid flooding with failed requests
                if (pollingIntervalId && (response.status === 404 || response.status === 500)) {
                    console.warn("Stopping polling due to server error.");
                    clearInterval(pollingIntervalId);
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const apiData = await response.json();
            
            if (!isPollingUpdate) { // Only log full data on initial load or manual refresh
            console.log("API Data:", apiData);
            } else {
                // console.log("Polling update received."); // Optional: for debugging polling
            }

            allNodesData = apiData.all_nodes; // Store for detail view

            if (apiData.overall_project_goal) {
                overallGoalDiv.textContent = `Overall Project Goal: ${apiData.overall_project_goal}`;
            } else {
                overallGoalDiv.textContent = 'Overall project goal not set.';
            }

            const visNodes = [];
            const visEdges = [];

            // Process nodes
            for (const nodeId in apiData.all_nodes) {
                const node = apiData.all_nodes[nodeId];
                const style = nodeTypeStyles[node.node_type] || nodeTypeStyles.EXECUTE; // Default to EXECUTE style

                // Construct node title (tooltip) including agent name if available
                let nodeTitle = `ID: ${node.task_id}\nGoal: ${node.goal}\nStatus: ${node.status || 'N/A'}\nLayer: ${node.layer}\nType: ${node.node_type}`;
                if (node.agent_name) {
                    nodeTitle += `\nAgent: ${node.agent_name}`;
                }

                visNodes.push({
                    id: node.task_id,
                    label: `${node.task_type || 'N/A'}${node.agent_name ? `\n(${node.agent_name.substring(0,15)})` : ''}\n${node.goal.substring(0, 25)}${node.goal.length > 25 ? '...' : ''}`, // Add agent name to label
                    title: nodeTitle, // Updated tooltip
                    level: node.layer,
                    // Apply specific style for node type, and override color by status
                    shape: style.shape,
                    font: style.font, // Font size can be adjusted here too for agent name
                    // size: style.size, // Uncomment if you want to set explicit size
                    color: {
                        background: statusColors[node.status] || '#E0E0E0', // Status color for background
                        border: style.color?.border || (statusColors[node.status] ? '#505050' : '#808080'), // Specific border or default
                        highlight: {
                            background: statusColors[node.status] ? lightenColor(statusColors[node.status], 20) : '#D0D0D0',
                            border: style.color?.highlight?.border || '#2B7CE9'
                        }
                    }
                });
            }

            // Process edges (dependencies within graphs and hierarchical links)
            for (const graphId in apiData.graphs) {
                const graph = apiData.graphs[graphId];
                // Dependency edges within this graph
                graph.edges.forEach(edge => {
                    visEdges.push({
                        from: edge.source,
                        to: edge.target,
                        arrows: 'to',
                        color: { color: '#3498DB', highlight:'#2980B9' }, // Brighter blue
                        width: 2, 
                    });
                });
            }
            
            // Add hierarchical edges from PLAN nodes to their direct sub-tasks
            // This uses parent_node_id. If a PLAN node itself creates a sub-graph,
            // its planned_sub_task_ids are its children.
            // For a more robust hierarchical layout, we might primarily rely on parent_node_id.
            for (const nodeId in apiData.all_nodes) {
                const node = apiData.all_nodes[nodeId];
                if (node.parent_node_id) {
                    // Check if the parent exists in the graph to avoid dangling edges
                    if (apiData.all_nodes[node.parent_node_id]) {
                         visEdges.push({
                            from: node.parent_node_id,
                            to: node.task_id,
                            arrows: 'to',
                            dashes: true, // Differentiate hierarchical links
                            color: { color: '#ADADAD', highlight:'#2196F3' },
                            // Optional: for hierarchical layout if not using level attribute directly
                            // length: 150 + (node.layer * 50) 
                        });
                    }
                }
            }


            const dataForNetwork = {
                nodes: new vis.DataSet(visNodes),
                edges: new vis.DataSet(visEdges.concat(contextFlowEdges.get())), // Includes dependency edges
            };

            const options = {
                layout: {
                    hierarchical: {
                        enabled: true,
                        levelSeparation: 220,    // Increased slightly
                        nodeSpacing: 160,      // Increased slightly
                        treeSpacing: 260,      // Increased slightly
                        direction: 'UD', 
                        sortMethod: 'directed', 
                        shakeTowards: 'roots',
                        edgeMinimization: true, // Try to minimize edge crossings
                        blockShifting: true,    // Allow blocks of nodes to shift
                        parentCentralization: true, // Center parent nodes above their children
                    },
                },
                physics: {
                    enabled: false, 
                },
                interaction: {
                    hover: true,
                    tooltipDelay: 200,
                    navigationButtons: true, // Adds zoom/fit buttons
                    keyboard: true,          // Allows keyboard navigation (zoom/move)
                },
                nodes: {
                    borderWidth: 2,
                    borderWidthSelected: 3,
                    font: {
                        color: '#343434',
                        size: 10, 
                        face: 'Segoe UI, Arial, sans-serif', // Match body font
                    },
                    // mass: 1, // Default mass, can be adjusted
                },
                edges: {
                    width: 1,
                    smooth: {
                        enabled: true,
                        type: "cubicBezier", // Good for hierarchical
                        forceDirection: "vertical", // "vertical" for UD, "horizontal" for LR
                        roundness: 0.4
                    },
                    // color: { inherit: 'from' } // Edges can inherit color from 'from' node
                }
            };

            if (!network) { // If first time, create the network
                network = new vis.Network(graphContainer, dataForNetwork, options);
                setupNetworkEventListeners(); // Setup listeners only once
            } else { // For updates, just set new data
                // Preserve view if possible (Vis.js might do this by default or need specific handling)
                // const currentView = network.getViewPosition();
                // const currentScale = network.getScale();
                
                network.setData(dataForNetwork);
                
                // network.moveTo({position: currentView, scale: currentScale}); // May cause issues with hierarchical
                // For hierarchical, it's usually best to let it re-layout.
                // Re-apply selection and context lines based on current state if needed,
                // but click handler will manage context lines.
                // We might need to re-trigger display of details if the selected node still exists.
                const detailsPre = document.getElementById('details-content');
                const existingSelectedNodeId = detailsPre.dataset.selectedNodeId;
                if (existingSelectedNodeId && allNodesData[existingSelectedNodeId]) {
                    // Re-render details for the currently selected node
                    renderNodeDetails(existingSelectedNodeId, allNodesData[existingSelectedNodeId]);
                    // Re-draw context lines for the selected node
                    drawContextLinesForSelectedNode(existingSelectedNodeId, allNodesData[existingSelectedNodeId]);
                } else if (existingSelectedNodeId) { 
                    // Selected node disappeared, clear details
                     detailsPre.innerHTML = '<h3>Node Details</h3><p>Previously selected node no longer exists. Click a node.</p>';
                     delete detailsPre.dataset.selectedNodeId;
                     contextFlowEdges.clear();
                     network.body.data.edges.update(contextFlowEdges.get()); // Refresh edges
                }
            }

            if (!showdownConverter) { // Initialize Showdown converter
                showdownConverter = new showdown.Converter({
                    tables: true, // Enable table support
                    strikethrough: true, // Enable strikethrough
                    tasklists: true, // Enable task lists
                    simpleLineBreaks: true // Convert single newlines to <br>
                });
            }

            if (!isPollingUpdate && !document.getElementById('legend-content').hasChildNodes()) { // Populate legend only once on initial load
                populateLegend();
            }

        } catch (error) {
            console.error('Failed to fetch or draw graph:', error);
            if (!isPollingUpdate) { // Show error on main div only for initial load problem
            overallGoalDiv.textContent = 'Failed to load graph data.';
                const detailsPre = document.getElementById('details-content');
                detailsPre.textContent = `Error: ${error.message}`;
            }
        }
    }

    function setupNetworkEventListeners() {
        if (!network) return;

        network.on('click', (params) => {
            contextFlowEdges.clear(); // Always clear context lines before potentially re-adding them

            const clickedNodeIds = params.nodes;
            const detailsPre = document.getElementById('details-content'); 

            if (clickedNodeIds.length > 0) {
                stopPolling(); // Pause polling when a node is selected
                const primaryNodeId = clickedNodeIds[0];
                const nodeData = allNodesData[primaryNodeId];
                
                detailsPre.dataset.selectedNodeId = primaryNodeId;
                renderNodeDetails(primaryNodeId, nodeData); 

                let selectionArray = [primaryNodeId]; 
                if (nodeData && nodeData.node_type === 'PLAN' && nodeData.planned_sub_task_ids && nodeData.planned_sub_task_ids.length > 0) {
                    nodeData.planned_sub_task_ids.forEach(subTaskId => {
                        if (allNodesData[subTaskId]) { selectionArray.push(subTaskId); }
                    });
                }
                network.setSelection({ nodes: selectionArray, edges: params.edges });

            } else { // Clicked on canvas
                detailsPre.innerHTML = '<h3>Node Details</h3><p>Click on a node to see its details here.</p>';
                delete detailsPre.dataset.selectedNodeId; 
                network.unselectAll();
                startPolling(); // Resume polling when canvas is clicked
            }
            
            if (network && network.body && network.body.data && network.body.data.edges) {
                network.body.data.edges.update(contextFlowEdges.get()); // Update edges (will be empty if showContextFlow is false or no context)
            }
        });
    }

    function renderNodeDetails(nodeId, nodeData) {
        const detailsPre = document.getElementById('details-content');
        detailsPre.innerHTML = ''; 

        if (nodeData) {
            const title = document.createElement('h3');
            title.textContent = `Details for Node: ${nodeId}`;
            detailsPre.appendChild(title);

            const dl = document.createElement('dl'); 
            const preferredOrder = [
                'goal', 'task_type', 'node_type', 'agent_name', 'status', 
                'layer', 'parent_node_id', 'sub_graph_id', 
                'output_summary', // Changed from result_summary
                'error', 'input_payload_summary',
                'timestamp_created', 'timestamp_updated', 'timestamp_completed'
            ];

            for (const key of preferredOrder) {
                if (nodeData.hasOwnProperty(key) && nodeData[key] !== null && nodeData[key] !== undefined) {
                    createDetailItem(dl, key, nodeData[key]);
                }
            }

            // Add any remaining keys (not objects/arrays we handle specially or already handled)
            for (const key in nodeData) {
                if (!preferredOrder.includes(key) && 
                    key !== 'input_context_sources' && 
                    key !== 'full_result' &&
                    nodeData.hasOwnProperty(key)) {
                     if (typeof nodeData[key] !== 'object' || nodeData[key] === null) {
                        createDetailItem(dl, key, nodeData[key]);
                    } else if (key === 'planned_sub_task_ids' && Array.isArray(nodeData[key])) {
                        createDetailItem(dl, key, nodeData[key].join(', ') || 'None');
                    }
                }
            }
            detailsPre.appendChild(dl);

            // Display Full Result (Collapsible)
            if (nodeData.hasOwnProperty('full_result') && nodeData.full_result !== null && nodeData.full_result !== undefined) {
                const resultSection = createCollapsibleSection(
                    "Full Result:",
                    (contentDiv) => {
                        if (typeof nodeData.full_result === 'string' && showdownConverter) {
                            try {
                                contentDiv.innerHTML = showdownConverter.makeHtml(nodeData.full_result);
                            } catch (e) {
                                console.error("Error converting markdown: ", e);
                                contentDiv.textContent = nodeData.full_result; // Fallback
                            }
                        } else if (typeof nodeData.full_result === 'object') {
                            const pre = document.createElement('pre');
                            pre.style.whiteSpace = 'pre-wrap';
                            pre.style.wordBreak = 'break-all';
                            pre.textContent = JSON.stringify(nodeData.full_result, null, 2);
                            contentDiv.appendChild(pre);
                        } else {
                            contentDiv.textContent = String(nodeData.full_result);
                        }
                    },
                    false // Initially collapsed: set to true to be initially expanded
                );
                resultSection.classList.add('result-content-section'); // Add class for specific styling if needed
                detailsPre.appendChild(resultSection);
            }

            // Display input context sources (Collapsible) - This is handled by drawContextLinesForSelectedNode
            // but we need to ensure drawContextLinesForSelectedNode appends to detailsPre correctly
            // and uses the collapsible pattern if desired. Let's refactor drawContextLinesForSelectedNode.

        } else {
            detailsPre.textContent = `Details not found for node ${nodeId}`;
        }
        
        // Call drawContextLinesForSelectedNode separately to ensure it's always processed
        // This will also handle its own collapsible section logic.
        drawContextLinesForSelectedNode(nodeId, nodeData); 
    }

    function drawContextLinesForSelectedNode(nodeId, nodeData) {
        // Do not clear contextFlowEdges here; it's managed by the caller (click handler or toggle)
        // contextFlowEdges.clear(); 

        const detailsPre = document.getElementById('details-content'); 
        
        const existingContextSection = detailsPre.querySelector('.context-sources-section');
        if (existingContextSection) {
            existingContextSection.remove();
        }

        if (nodeData && nodeData.input_context_sources && nodeData.input_context_sources.length > 0) {
            const contextSection = createCollapsibleSection(
                "Input Context Sources:",
                (contentDiv) => {
                    const contextUl = document.createElement('ul');
                    contextUl.id = 'context-sources-list';
                    contextUl.style.paddingLeft = '0px'; 
                    
                    if (showContextFlow) { // <--- Only add edges if toggle is on
                        nodeData.input_context_sources.forEach(source => {
                            const li = document.createElement('li');
                            li.innerHTML = `From Task: <code>${source.source_task_id}</code><br>` +
                                           `&nbsp;&nbsp;Goal: <i>${source.source_task_goal_summary}</i><br>` +
                                           `&nbsp;&nbsp;Type: ${source.content_type}`;
                            contextUl.appendChild(li);
                            if (allNodesData[source.source_task_id]) {
                                contextFlowEdges.add({
                                    from: source.source_task_id,
                                    to: nodeId,
                                    arrows: 'to', dashes: [5, 5],
                                    color: { color: '#FF69B4', highlight: '#FF1493' },
                                    physics: false, label: source.content_type_description ? source.content_type_description.substring(0,15) : ""
                                });
                            }
                        });
                    } else { // Still list them but don't draw lines
                         nodeData.input_context_sources.forEach(source => {
                            const li = document.createElement('li');
                            li.innerHTML = `From Task: <code>${source.source_task_id}</code><br>` +
                                           `&nbsp;&nbsp;Goal: <i>${source.source_task_goal_summary}</i><br>` +
                                           `&nbsp;&nbsp;Type: ${source.content_type}`;
                            contextUl.appendChild(li);
                        });
                    }
                    contentDiv.appendChild(contextUl);
                },
                true 
            );
            contextSection.classList.add('context-sources-section');
            detailsPre.appendChild(contextSection);
        } else if (nodeData) { // Node data exists, but no context sources
            const noContextSection = document.createElement('div');
            noContextSection.className = 'context-sources-section'; // Keep class for potential removal
            const p = document.createElement('p');
            p.style.fontStyle = 'italic';
            p.style.color = '#555';
            p.textContent = "Input Context Sources: None";
            
            const title = document.createElement('h4');
            title.textContent = "Input Context Sources:";
            title.style.marginTop = '15px';
            title.style.marginBottom = '8px';
            noContextSection.appendChild(title);
            noContextSection.appendChild(p);
            detailsPre.appendChild(noContextSection);
        }
        // The actual update of edges on the graph is handled in the main click handler
        // or after setData in the polling update.
    }

    function createCollapsibleSection(titleText, populateContentCallback, initiallyExpanded = false) {
        const sectionDiv = document.createElement('div');
        sectionDiv.className = 'collapsible-section';

        const header = document.createElement('h4');
        header.className = 'collapsible-header';
        header.innerHTML = `<span class="toggler">${initiallyExpanded ? '&#9660;' : '&#9654;'}</span> ${titleText}`; // Down/Right arrow

        const contentDiv = document.createElement('div');
        contentDiv.className = 'collapsible-content';
        if (initiallyExpanded) {
            contentDiv.style.display = 'block';
        } else {
            contentDiv.style.display = 'none';
        }
        
        populateContentCallback(contentDiv); // Let the caller fill the content

        header.addEventListener('click', () => {
            const isHidden = contentDiv.style.display === 'none';
            contentDiv.style.display = isHidden ? 'block' : 'none';
            header.querySelector('.toggler').innerHTML = isHidden ? '&#9660;' : '&#9654;'; // Update arrow
        });

        sectionDiv.appendChild(header);
        sectionDiv.appendChild(contentDiv);
        return sectionDiv;
    }

    function createDetailItem(dlElement, term, details, allowPreformat = false) {
        const dt = document.createElement('dt');
        dt.textContent = term.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        const dd = document.createElement('dd');
        if (allowPreformat && typeof details === 'object' && details !== null) {
            const pre = document.createElement('pre');
            pre.style.whiteSpace = 'pre-wrap';
            pre.style.wordBreak = 'break-all';
            pre.textContent = JSON.stringify(details, null, 2);
            dd.appendChild(pre);
        } else if (typeof details === 'object' && details !== null) {
             dd.textContent = JSON.stringify(details); // Default for other objects if not preformatted
        } else {
            dd.textContent = details === null || details === undefined ? 'N/A' : String(details);
        }
        dlElement.appendChild(dt);
        dlElement.appendChild(dd);
    }

    // Helper function to lighten a hex color (for highlight)
    function lightenColor(hex, percent) {
        hex = hex.replace(/^#/, '');
        let r = parseInt(hex.substring(0, 2), 16);
        let g = parseInt(hex.substring(2, 4), 16);
        let b = parseInt(hex.substring(4, 6), 16);

        r = Math.min(255, r + Math.floor(255 * (percent / 100)));
        g = Math.min(255, g + Math.floor(255 * (percent / 100)));
        b = Math.min(255, b + Math.floor(255 * (percent / 100)));

        return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
    }

    function populateLegend() {
        const legendContent = document.getElementById('legend-content');
        legendContent.innerHTML = ''; // Clear any existing legend items

        // === Node Statuses ===
        const statusSection = document.createElement('div');
        statusSection.className = 'legend-section';
        const statusTitle = document.createElement('h4');
        statusTitle.textContent = 'Node Statuses';
        statusSection.appendChild(statusTitle);
        for (const status in statusColors) {
            const item = document.createElement('div');
            item.className = 'legend-item';
            const symbol = document.createElement('span');
            symbol.className = 'symbol';
            symbol.style.backgroundColor = statusColors[status];
            const label = document.createElement('span');
            label.className = 'label';
            label.textContent = status.replace(/_/g, ' '); // Format status name
            item.appendChild(symbol);
            item.appendChild(label);
            statusSection.appendChild(item);
        }
        legendContent.appendChild(statusSection);

        // === Node Types ===
        const typeSection = document.createElement('div');
        typeSection.className = 'legend-section';
        const typeTitle = document.createElement('h4');
        typeTitle.textContent = 'Node Types';
        typeSection.appendChild(typeTitle);
        for (const type in nodeTypeStyles) {
            const style = nodeTypeStyles[type];
            const item = document.createElement('div');
            item.className = 'legend-item';
            const symbol = document.createElement('span');
            symbol.className = 'symbol';
            // Simulate shape approximately with CSS
            symbol.style.backgroundColor = '#f0f0f0'; // Neutral background for shape demo
            if (style.shape === 'box') {
                symbol.style.borderRadius = '0';
            } else if (style.shape === 'ellipse') {
                symbol.style.borderRadius = '50%';
            } // Add more shapes if needed
            const label = document.createElement('span');
            label.className = 'label';
            label.textContent = style.label || type;
            item.appendChild(symbol);
            item.appendChild(label);
            typeSection.appendChild(item);
        }
        legendContent.appendChild(typeSection);

        // === Edge Types ===
        const edgeSection = document.createElement('div');
        edgeSection.className = 'legend-section';
        const edgeTitle = document.createElement('h4');
        edgeTitle.textContent = 'Edge Types';
        edgeSection.appendChild(edgeTitle);
        edgeLegendStyles.forEach(edgeStyle => {
            const item = document.createElement('div');
            item.className = 'legend-item';
            const symbol = document.createElement('span');
            symbol.className = 'line-symbol';
            symbol.style.backgroundColor = edgeStyle.dashes ? 'transparent' : edgeStyle.color; // For solid line
            if (edgeStyle.dashes) {
                symbol.classList.add('dashed');
                symbol.style.borderColor = edgeStyle.color; // Dashed line color
            }
            const label = document.createElement('span');
            label.className = 'label';
            label.textContent = edgeStyle.label;
            item.appendChild(symbol);
            item.appendChild(label);
            edgeSection.appendChild(item);
        });
        legendContent.appendChild(edgeSection);
    }

    if (startProjectButton) { // Ensure the button exists
        startProjectButton.addEventListener('click', async () => {
            const goal = projectGoalInput.value.trim();
            if (!goal) {
                projectStatusMessage.textContent = 'Please enter a project goal.';
                projectStatusMessage.style.color = 'red';
                return;
            }

            projectStatusMessage.textContent = 'Initiating project...';
            projectStatusMessage.style.color = 'blue';

            try {
                const response = await fetch('http://127.0.0.1:5000/api/start-project', { // <--- USE FULL URL HERE
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ project_goal: goal, max_steps: 125 }),
                });

                const result = await response.json();

                if (response.ok) {
                    projectStatusMessage.textContent = result.message || 'Project started successfully!';
                    projectStatusMessage.style.color = 'green';
                    // Optionally, clear the input field
                    // projectGoalInput.value = ''; 
                    // Trigger an immediate graph refresh, polling will also continue
                    fetchAndDrawGraph(); 
                } else {
                    projectStatusMessage.textContent = `Error: ${result.error || 'Failed to start project.'}`;
                    projectStatusMessage.style.color = 'red';
                }
            } catch (error) {
                console.error('Error starting project:', error);
                projectStatusMessage.textContent = 'Network error or server unavailable.';
                projectStatusMessage.style.color = 'red';
            }
        });
    }

    // Initial fetch (will show empty or last state if server was running)
    fetchAndDrawGraph();

    // Start polling
    // pollingIntervalId = setInterval(() => { // Old way
    //     fetchAndDrawGraph(true); 
    // }, POLLING_INTERVAL);
    startPolling(); // New way

    // Setup for context flow toggle
    contextFlowToggle = document.getElementById('show-context-flow-checkbox');
    if (contextFlowToggle) {
        showContextFlow = contextFlowToggle.checked; // Initialize from checkbox's default state

        contextFlowToggle.addEventListener('change', () => {
            showContextFlow = contextFlowToggle.checked;
            contextFlowEdges.clear(); // Clear existing lines

            const selectedNodeId = detailsContent.dataset.selectedNodeId;
            if (selectedNodeId && allNodesData[selectedNodeId]) {
                const nodeData = allNodesData[selectedNodeId];
                // Re-populate based on current selection and new toggle state
                // (drawContextLinesForSelectedNode's logic for adding edges will respect showContextFlow)
                // We essentially need to call the part of drawContextLinesForSelectedNode that adds to contextFlowEdges
                if (showContextFlow && nodeData.input_context_sources) {
                     nodeData.input_context_sources.forEach(source => {
                        if (allNodesData[source.source_task_id]) {
                            contextFlowEdges.add({
                                from: source.source_task_id,
                                to: selectedNodeId,
                                arrows: 'to', dashes: [5, 5],
                                color: { color: '#FF69B4', highlight: '#FF1493' },
                                physics: false, label: source.content_type_description ? source.content_type_description.substring(0,15) : ""
                            });
                        }
                    });
                }
            }
            // Update the graph's edges
            if (network && network.body && network.body.data && network.body.data.edges) {
                network.body.data.edges.update(contextFlowEdges.get());
            }
        });
    }
});