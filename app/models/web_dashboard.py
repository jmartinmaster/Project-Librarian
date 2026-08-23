# Copyright (C) 2026 The Librarian contributors
#
# This file is part of The Librarian.
#
# The Librarian is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# The Librarian is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with The Librarian. If not, see <https://www.gnu.org/licenses/>.
"""Web dashboard and interactive UI template for Project Librarian MCP/FastAPI runtime."""

from __future__ import annotations


def get_web_dashboard_html() -> str:
    """Return the standalone, high-fidelity HTML/CSS/JS dashboard for The Librarian."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>The Librarian - Codebase Intelligence & MCP Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --bg-card: rgba(22, 27, 34, 0.85);
            --border-color: #30363d;
            --border-hover: #58a6ff;
            --text-primary: #f0f6fc;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;
            --accent-blue: #58a6ff;
            --accent-green: #3fb950;
            --accent-purple: #bc8cff;
            --accent-orange: #f0883e;
            --accent-red: #f85149;
            --accent-cyan: #39c5cf;
            --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
            --radius-sm: 6px;
            --radius-md: 10px;
            --radius-lg: 14px;
            --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.3);
            --shadow-md: 0 4px 20px rgba(0, 0, 0, 0.5);
            --shadow-glow: 0 0 20px rgba(88, 166, 255, 0.15);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: var(--font-sans);
            background: radial-gradient(circle at 50% 0%, #171d26 0%, var(--bg-primary) 70%);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }

        /* Top Navbar */
        header.navbar {
            background: rgba(13, 17, 23, 0.85);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border-color);
            position: sticky;
            top: 0;
            z-index: 100;
            padding: 0.75rem 1.5rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .brand-container {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .brand-logo {
            font-size: 1.5rem;
            line-height: 1;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            background: rgba(63, 185, 80, 0.15);
            color: var(--accent-green);
            border: 1px solid rgba(63, 185, 80, 0.3);
            border-radius: 20px;
            padding: 0.2rem 0.65rem;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.3px;
        }

        .status-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background-color: var(--accent-green);
            box-shadow: 0 0 8px var(--accent-green);
            animation: pulse-green 2s infinite;
        }

        @keyframes pulse-green {
            0%, 100% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.3); opacity: 0.6; }
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .repo-badge {
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            font-family: var(--font-mono);
            font-size: 0.8rem;
            padding: 0.35rem 0.75rem;
            border-radius: var(--radius-sm);
            max-width: 320px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .btn {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            font-family: var(--font-sans);
            font-size: 0.825rem;
            font-weight: 500;
            padding: 0.4rem 0.85rem;
            border-radius: var(--radius-sm);
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            text-decoration: none;
        }

        .btn:hover {
            background: var(--bg-tertiary);
            border-color: var(--text-secondary);
            transform: translateY(-1px);
        }

        .btn-primary {
            background: #238636;
            border-color: #2ea043;
            color: #ffffff;
            font-weight: 600;
        }

        .btn-primary:hover {
            background: #2ea043;
            border-color: #3fb950;
            box-shadow: 0 0 12px rgba(46, 160, 67, 0.4);
        }

        .btn-blue {
            background: #1f6feb;
            border-color: #388bfd;
            color: #ffffff;
        }

        .btn-blue:hover {
            background: #388bfd;
            box-shadow: 0 0 12px rgba(56, 139, 253, 0.4);
        }

        /* Main Tabs Layout */
        .tabs-nav {
            display: flex;
            gap: 0.5rem;
            border-bottom: 1px solid var(--border-color);
            padding: 0 1.5rem;
            background: var(--bg-secondary);
        }

        .tab-btn {
            background: transparent;
            border: none;
            color: var(--text-secondary);
            font-family: var(--font-sans);
            font-size: 0.875rem;
            font-weight: 500;
            padding: 0.75rem 1rem;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .tab-btn:hover {
            color: var(--text-primary);
        }

        .tab-btn.active {
            color: var(--accent-blue);
            border-bottom-color: var(--accent-blue);
            font-weight: 600;
        }

        /* App Container */
        .app-container {
            max-width: 1300px;
            width: 100%;
            margin: 1.5rem auto;
            padding: 0 1.5rem;
            flex: 1;
        }

        .tab-content {
            display: none;
            animation: fadeIn 0.25s ease-in-out;
        }

        .tab-content.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(4px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Glass Card */
        .card {
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-sm);
            padding: 1.25rem;
            margin-bottom: 1.5rem;
        }

        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid var(--border-color);
        }

        .card-title {
            font-size: 1.05rem;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        /* Search Bar & Chips */
        .search-box-wrapper {
            position: relative;
            margin-bottom: 1rem;
        }

        .search-input {
            width: 100%;
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            color: var(--text-primary);
            font-family: var(--font-sans);
            font-size: 0.95rem;
            padding: 0.75rem 1rem 0.75rem 2.5rem;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }

        .search-input:focus {
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.2);
        }

        .search-icon {
            position: absolute;
            left: 0.85rem;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-secondary);
            pointer-events: none;
        }

        .filter-chips {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin-bottom: 1rem;
        }

        .chip {
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            border-radius: 20px;
            padding: 0.25rem 0.75rem;
            font-size: 0.775rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }

        .chip:hover, .chip.active {
            background: rgba(88, 166, 255, 0.15);
            border-color: var(--accent-blue);
            color: var(--accent-blue);
        }

        /* Results List */
        .results-container {
            display: flex;
            flex-direction: column;
            gap: 0.6rem;
            max-height: 600px;
            overflow-y: auto;
            padding-right: 0.25rem;
        }

        .result-item {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-sm);
            padding: 0.85rem 1rem;
            transition: all 0.2s;
            cursor: pointer;
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
        }

        .result-item:hover {
            border-color: var(--accent-blue);
            background: rgba(88, 166, 255, 0.05);
            transform: translateX(3px);
        }

        .result-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .result-name-group {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .result-name {
            font-family: var(--font-mono);
            font-size: 0.925rem;
            font-weight: 600;
            color: var(--accent-blue);
        }

        .kind-badge {
            font-size: 0.675rem;
            font-weight: 700;
            text-transform: uppercase;
            padding: 0.15rem 0.45rem;
            border-radius: 4px;
            letter-spacing: 0.5px;
        }

        .kind-class { background: rgba(188, 140, 255, 0.15); color: var(--accent-purple); border: 1px solid rgba(188, 140, 255, 0.3); }
        .kind-method, .kind-function { background: rgba(88, 166, 255, 0.15); color: var(--accent-blue); border: 1px solid rgba(88, 166, 255, 0.3); }
        .kind-file { background: rgba(63, 185, 80, 0.15); color: var(--accent-green); border: 1px solid rgba(63, 185, 80, 0.3); }
        .kind-excel_row { background: rgba(240, 136, 62, 0.15); color: var(--accent-orange); border: 1px solid rgba(240, 136, 62, 0.3); }

        .result-meta {
            font-family: var(--font-mono);
            font-size: 0.775rem;
            color: var(--text-secondary);
        }

        .result-doc {
            font-size: 0.825rem;
            color: var(--text-secondary);
            line-height: 1.4;
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }

        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            padding: 1rem 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }

        .stat-label {
            font-size: 0.8rem;
            font-weight: 500;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .stat-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-primary);
            font-family: var(--font-mono);
        }

        /* Code & Pre Box */
        pre.code-view {
            background: #090d13;
            border: 1px solid var(--border-color);
            border-radius: var(--radius-sm);
            padding: 1rem;
            color: #c9d1d9;
            font-family: var(--font-mono);
            font-size: 0.85rem;
            overflow-x: auto;
            max-height: 500px;
        }

        /* Form Inputs & Controls */
        .form-row {
            display: flex;
            gap: 0.75rem;
            margin-bottom: 1rem;
        }

        .form-control {
            flex: 1;
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-sm);
            color: var(--text-primary);
            font-family: var(--font-sans);
            font-size: 0.875rem;
            padding: 0.5rem 0.75rem;
            outline: none;
        }

        .form-control:focus {
            border-color: var(--accent-blue);
        }

        /* Table */
        .data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }

        .data-table th, .data-table td {
            padding: 0.65rem 0.85rem;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }

        .data-table th {
            color: var(--text-secondary);
            font-weight: 600;
            background: rgba(22, 27, 34, 0.6);
        }

        .data-table tr:hover td {
            background: rgba(88, 166, 255, 0.05);
        }

        /* Severity Badges */
        .sev-badge {
            font-size: 0.7rem;
            font-weight: 700;
            padding: 0.15rem 0.45rem;
            border-radius: 4px;
            text-transform: uppercase;
        }

        .sev-error { background: rgba(248, 81, 73, 0.2); color: var(--accent-red); border: 1px solid rgba(248, 81, 73, 0.4); }
        .sev-warning { background: rgba(240, 136, 62, 0.2); color: var(--accent-orange); border: 1px solid rgba(240, 136, 62, 0.4); }
        .sev-info { background: rgba(88, 166, 255, 0.2); color: var(--accent-blue); border: 1px solid rgba(88, 166, 255, 0.4); }

        footer {
            margin-top: auto;
            padding: 1.5rem;
            text-align: center;
            font-size: 0.8rem;
            color: var(--text-muted);
            border-top: 1px solid var(--border-color);
            background: var(--bg-primary);
        }
    </style>
</head>
<body>

    <!-- Header Navbar -->
    <header class="navbar">
        <div class="brand-container">
            <div class="brand-logo">📚 The Librarian</div>
            <div class="status-pill">
                <span class="status-dot"></span>
                <span>MCP LIVE</span>
            </div>
        </div>
        <div class="header-actions">
            <span class="repo-badge" id="repoRootBadge" title="Active Workspace Root">Loading workspace...</span>
            <button class="btn btn-primary" id="btnRefreshIndex" onclick="triggerRefresh()">
                <span id="refreshIcon">↺</span> Refresh Index
            </button>
            <a href="/docs" target="_blank" class="btn" title="Open FastAPI Interactive OpenAPI Docs">
                <span>⚡</span> OpenAPI Docs
            </a>
        </div>
    </header>

    <!-- Top Tabs Navigation -->
    <nav class="tabs-nav">
        <button class="tab-btn active" onclick="switchTab('searchTab', this)">🔍 Search & Symbols</button>
        <button class="tab-btn" onclick="switchTab('astTab', this)">🌳 AST & CST Inspector</button>
        <button class="tab-btn" onclick="switchTab('callGraphTab', this)">🕸️ Call Graph &amp; Dependencies</button>
        <button class="tab-btn" onclick="switchTab('auditTab', this)">🛡️ Code Audit</button>
        <button class="tab-btn" onclick="switchTab('mcpTab', this)">⚙️ MCP Tools & Playground</button>
        <button class="tab-btn" onclick="switchTab('statusTab', this)">📊 Server Status</button>
    </nav>

    <!-- Main Content Container -->
    <main class="app-container">

        <!-- Quick Stats Overview -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Indexed Symbols</div>
                <div class="stat-value" id="statSymbolsCount">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Indexed Files</div>
                <div class="stat-value" id="statFilesCount">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Auto-Refresh Interval</div>
                <div class="stat-value" id="statRefreshInterval">30s</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Last Refresh</div>
                <div class="stat-value" id="statLastRefresh" style="font-size: 1rem; font-weight: 500;">Just now</div>
            </div>
        </div>

        <!-- TAB 1: Search & Symbols -->
        <section id="searchTab" class="tab-content active">
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Codebase Search & Symbol Explorer</div>
                    <span id="searchResultCount" style="font-size: 0.85rem; color: var(--text-secondary);">Showing all symbols</span>
                </div>

                <div class="search-box-wrapper">
                    <span class="search-icon">🔍</span>
                    <input type="text" id="searchInput" class="search-input" placeholder="Search functions, classes, files, signatures, or Excel rows..." oninput="onSearchInput(this.value)">
                </div>

                <div class="filter-chips">
                    <button class="chip active" onclick="setSearchScope('all', this)">All</button>
                    <button class="chip" onclick="setSearchScope('symbols', this)">Symbols</button>
                    <button class="chip" onclick="setSearchScope('files', this)">Files</button>
                    <button class="chip" onclick="setSearchScope('excel_rows', this)">Excel Rows</button>
                </div>

                <div class="results-container" id="searchResultsList">
                    <div style="text-align: center; color: var(--text-secondary); padding: 2rem;">Loading index snapshot...</div>
                </div>
            </div>
        </section>

        <!-- TAB 2: AST & CST Inspector -->
        <section id="astTab" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <div class="card-title">AST & CST Concrete Structure Viewer</div>
                    <span style="font-size: 0.8rem; color: var(--text-secondary);">libcst & pycparser engine</span>
                </div>

                <div class="form-row">
                    <input type="text" id="astPathInput" class="form-control" placeholder="Enter relative path (e.g. main.py, app/config.py, psram_tool.c)...">
                    <button class="btn btn-blue" onclick="loadAst()">Parse Structure</button>
                </div>

                <div id="astOutputContainer">
                    <pre class="code-view" id="astCodeView">// Select a file or click 'Inspect AST' from search results to view AST/CST metadata</pre>
                </div>
            </div>
        </section>

        <!-- TAB: Call Graph & Dependencies -->
        <section id="callGraphTab" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Symbol Call Graph &amp; Reference Explorer</div>
                    <span id="callGraphStatusBadge" style="font-size: 0.85rem; color: var(--text-secondary);">Enter symbol to trace</span>
                </div>

                <div class="search-box-wrapper" style="display: flex; gap: 0.5rem;">
                    <input type="text" id="callGraphInput" class="search-input" style="padding-left: 1rem;" placeholder="Enter function, class, struct, or macro name (e.g. run_mcp_server, IndexManager)..." onkeydown="if(event.key==='Enter') executeCallGraph()">
                    <button class="btn btn-primary" onclick="executeCallGraph()">Trace Hierarchy</button>
                </div>

                <div id="callGraphTargetCard" style="display: none; background: rgba(22, 27, 34, 0.7); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 0.85rem; margin-bottom: 1rem;">
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <div>
                            <span id="cgTargetKind" class="tag" style="background: rgba(88, 166, 255, 0.2); color: var(--accent-blue); font-weight: 700; text-transform: uppercase;">FUNCTION</span>
                            <strong id="cgTargetName" style="margin-left: 0.5rem; font-size: 1.05rem;">symbol_name</strong>
                        </div>
                        <span id="cgTargetLoc" style="color: var(--text-secondary); font-family: var(--font-mono); font-size: 0.85rem;">path:line</span>
                    </div>
                    <div id="cgTargetDoc" style="color: var(--text-muted); font-size: 0.85rem; margin-top: 0.4rem; font-style: italic;">Docstring</div>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                    <div>
                        <h4 style="margin-bottom: 0.5rem; font-size: 0.95rem; color: var(--text-secondary);">Incoming Callers &amp; References (<span id="cgCallerCount">0</span>)</h4>
                        <div id="cgCallersList" style="max-height: 400px; overflow-y: auto; display: flex; flex-direction: column; gap: 0.5rem;">
                            <div style="color: var(--text-muted); font-size: 0.85rem;">No symbol queried yet.</div>
                        </div>
                    </div>
                    <div>
                        <h4 style="margin-bottom: 0.5rem; font-size: 0.95rem; color: var(--text-secondary);">Outgoing Callees</h4>
                        <div id="cgCalleesList" style="max-height: 200px; overflow-y: auto; display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 1rem;">
                            <div style="color: var(--text-muted); font-size: 0.85rem;">No outgoing calls.</div>
                        </div>
                        <h4 style="margin-bottom: 0.5rem; font-size: 0.95rem; color: var(--text-secondary);">Module Imports</h4>
                        <div id="cgImportsList" style="max-height: 180px; overflow-y: auto; display: flex; flex-direction: column; gap: 0.3rem;">
                            <div style="color: var(--text-muted); font-size: 0.85rem;">No imports.</div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- TAB 3: Code Audit -->
        <section id="auditTab" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Code Quality & Anti-Pattern Audit</div>
                    <button class="btn btn-blue" onclick="runAudit()">Run Audit Scan</button>
                </div>

                <div id="auditResultsContainer">
                    <p style="color: var(--text-secondary); font-size: 0.9rem;">Click <strong>Run Audit Scan</strong> to perform full anti-pattern and formatting diagnostics across your active workspace.</p>
                </div>
            </div>
        </section>

        <!-- TAB 4: MCP Tools & Playground -->
        <section id="mcpTab" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Model Context Protocol (MCP) JSON-RPC Playground</div>
                </div>

                <div class="form-row">
                    <button class="btn" onclick="setJsonRpcPayload('ping', {})">⚡ Ping</button>
                    <button class="btn" onclick="setJsonRpcPayload('probe', {})">🔍 Probe Capabilities</button>
                    <button class="btn" onclick="setJsonRpcPayload('search', {'q': 'MainWindowView', 'limit': 5})">🔎 Search Query</button>
                    <button class="btn" onclick="setJsonRpcPayload('ast', {'path': 'main.py'})">🌳 AST Tree</button>
                </div>

                <div style="margin-bottom: 1rem;">
                    <textarea id="jsonRpcInput" class="form-control" style="font-family: var(--font-mono); height: 120px; font-size: 0.85rem;" placeholder="Enter JSON-RPC request payload..."></textarea>
                </div>

                <button class="btn btn-primary" onclick="sendJsonRpc()">Send JSON-RPC Request</button>

                <div style="margin-top: 1rem;">
                    <div style="font-size: 0.85rem; font-weight: 600; margin-bottom: 0.5rem; color: var(--text-secondary);">Response:</div>
                    <pre class="code-view" id="jsonRpcOutput">// Response will appear here...</pre>
                </div>
            </div>
        </section>

        <!-- TAB 5: Server Status -->
        <section id="statusTab" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Server Runtime & Architecture Status</div>
                    <button class="btn" onclick="loadStatus()">Refresh Status</button>
                </div>

                <table class="data-table" id="statusDetailsTable">
                    <tbody>
                        <tr><th>Server Runtime</th><td>Project Librarian (FastAPI + FastMCP)</td></tr>
                        <tr><th>Active Repo Root</th><td id="tableRepoRoot">-</td></tr>
                        <tr><th>Auto-Refresh Worker</th><td id="tableWorkerRunning">-</td></tr>
                        <tr><th>Refresh Interval</th><td id="tableRefreshInterval">-</td></tr>
                        <tr><th>Refresh Count</th><td id="tableRefreshCount">-</td></tr>
                        <tr><th>Skipped Refreshes</th><td id="tableSkippedCount">-</td></tr>
                        <tr><th>Last Refresh Timestamp</th><td id="tableLastRefresh">-</td></tr>
                    </tbody>
                </table>
            </div>

            <div class="card">
                <div class="card-header">
                    <div class="card-title">Available REST & MCP Endpoints</div>
                </div>
                <table class="data-table">
                    <thead>
                        <tr><th>Method</th><th>Endpoint</th><th>Description</th></tr>
                    </thead>
                    <tbody>
                        <tr><td><code>GET</code></td><td><a href="/api/mcp-probe" target="_blank" style="color: var(--accent-blue);">/api/mcp-probe</a></td><td>Server capabilities, route inventory, and authentication schema</td></tr>
                        <tr><td><code>GET</code></td><td><a href="/api/status" target="_blank" style="color: var(--accent-blue);">/api/status</a></td><td>Real-time indexing status, worker state, and repository root</td></tr>
                        <tr><td><code>GET / POST</code></td><td><a href="/api/search?q=" target="_blank" style="color: var(--accent-blue);">/api/search</a></td><td>Search file corpus, Python/C symbols, and Excel datasets</td></tr>
                        <tr><td><code>GET / POST</code></td><td><a href="/api/ast?path=main.py" target="_blank" style="color: var(--accent-blue);">/api/ast</a></td><td>Extract concrete CST & AST structure from source files</td></tr>
                        <tr><td><code>POST</code></td><td><code>/api/server/refresh</code></td><td>Trigger an on-demand asynchronous codebase indexing cycle</td></tr>
                        <tr><td><code>POST</code></td><td><code>/api/mcp-probe/jsonrpc</code></td><td>Unified JSON-RPC protocol endpoint for MCP clients</td></tr>
                        <tr><td><code>GET / POST</code></td><td><code>/mcp/sse</code></td><td>FastMCP Server-Sent Events (SSE) stream endpoint</td></tr>
                        <tr><td><code>GET</code></td><td><a href="/docs" target="_blank" style="color: var(--accent-blue);">/docs</a></td><td>Interactive Swagger / OpenAPI documentation interface</td></tr>
                    </tbody>
                </table>
            </div>
        </section>

    </main>

    <footer>
        Project Librarian &bull; Local Codebase Intelligence, MicroPython IDE &amp; Model Context Protocol Runtime
    </footer>

    <script>
        let currentScope = 'all';
        let searchDebounceTimer = null;

        // Tab Switching
        function switchTab(tabId, btn) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            btn.classList.add('active');

            if (tabId === 'statusTab') loadStatus();
        }

        function setSearchScope(scope, chip) {
            currentScope = scope;
            document.querySelectorAll('.filter-chips .chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            performSearch(document.getElementById('searchInput').value);
        }

        function onSearchInput(val) {
            clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(() => performSearch(val), 200);
        }

        async function performSearch(query = '') {
            try {
                const resp = await fetch(`/api/search?q=${encodeURIComponent(query)}&scope=${currentScope}&limit=100`);
                if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                const data = await resp.json();
                renderSearchResults(data.results || []);
            } catch (err) {
                document.getElementById('searchResultsList').innerHTML = `<div style="color: var(--accent-red); padding: 1rem;">Search error: ${err.message}</div>`;
            }
        }

        function renderSearchResults(results) {
            const container = document.getElementById('searchResultsList');
            document.getElementById('searchResultCount').innerText = `${results.length} result(s) found`;
            
            if (results.length === 0) {
                container.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 2rem;">No matching symbols or files found.</div>';
                return;
            }

            container.innerHTML = results.map(item => {
                const kind = item.type || item.kind || 'symbol';
                const name = item.name || item.title || item.file_path || 'Unnamed';
                const path = item.file_path || item.path || '';
                const line = item.line ? `Line ${item.line}` : '';
                const doc = item.docstring || item.doc_summary || item.snippet || '';
                const sig = item.signature || '';

                return `
                    <div class="result-item" onclick="inspectFileAst('${path}')">
                        <div class="result-top">
                            <div class="result-name-group">
                                <span class="kind-badge kind-${kind}">${kind}</span>
                                <span class="result-name">${escapeHtml(name)}</span>
                            </div>
                            <span class="result-meta">${escapeHtml(path)} ${line ? ' &bull; ' + line : ''}</span>
                        </div>
                        ${sig ? `<div style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--accent-cyan);">${escapeHtml(sig)}</div>` : ''}
                        ${doc ? `<div class="result-doc">${escapeHtml(doc)}</div>` : ''}
                    </div>
                `;
            }).join('');
        }

        function inspectFileAst(path) {
            if (!path) return;
            document.getElementById('astPathInput').value = path;
            switchTab('astTab', document.querySelectorAll('.tab-btn')[1]);
            loadAst();
        }

        async function loadAst() {
            const path = document.getElementById('astPathInput').value.trim();
            if (!path) return;
            const output = document.getElementById('astCodeView');
            output.innerText = 'Parsing AST & CST structures...';

            try {
                const resp = await fetch('/api/ast', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path })
                });
                if (!resp.ok) {
                    const err = await resp.json();
                    output.innerText = `Error: ${err.detail || 'Could not parse file'}`;
                    return;
                }
                const data = await resp.json();
                output.innerText = JSON.stringify(data, null, 2);
            } catch (e) {
                output.innerText = `Network error: ${e.message}`;
            }
        }

        async function runAudit() {
            const container = document.getElementById('auditResultsContainer');
            container.innerHTML = '<p style="color: var(--text-secondary);">Running anti-pattern and formatting scan...</p>';

            try {
                const resp = await fetch('/api/mcp-probe/jsonrpc', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ method: 'audit_triad', params: {} })
                });
                const res = await resp.json();
                const issues = res.result || [];

                if (!Array.isArray(issues) || issues.length === 0) {
                    container.innerHTML = '<div style="background: rgba(63, 185, 80, 0.1); border: 1px solid rgba(63, 185, 80, 0.3); padding: 1rem; border-radius: var(--radius-sm); color: var(--accent-green); font-weight: 600;">✓ Clean Codebase: No anti-patterns or formatting errors detected!</div>';
                    return;
                }

                container.innerHTML = `
                    <table class="data-table">
                        <thead>
                            <tr><th>Severity</th><th>Rule</th><th>File & Line</th><th>Description</th></tr>
                        </thead>
                        <tbody>
                            ${issues.map(iss => `
                                <tr>
                                    <td><span class="sev-badge sev-${(iss.severity || 'warning').toLowerCase()}">${escapeHtml(iss.severity || 'warning')}</span></td>
                                    <td><strong>${escapeHtml(iss.preset_name || iss.rule || '')}</strong></td>
                                    <td style="font-family: var(--font-mono); font-size: 0.775rem;">${escapeHtml(iss.path || '')}:${iss.line || ''}</td>
                                    <td>${escapeHtml(iss.description || iss.message || '')}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
            } catch (e) {
                container.innerHTML = `<div style="color: var(--accent-red);">Audit scan failed: ${e.message}</div>`;
            }
        }

        function setJsonRpcPayload(method, params) {
            document.getElementById('jsonRpcInput').value = JSON.stringify({
                jsonrpc: '2.0',
                id: Date.now(),
                method,
                params
            }, null, 2);
        }

        async function sendJsonRpc() {
            const raw = document.getElementById('jsonRpcInput').value.trim();
            const output = document.getElementById('jsonRpcOutput');
            output.innerText = 'Sending request...';

            try {
                const parsed = JSON.parse(raw);
                const resp = await fetch('/api/mcp-probe/jsonrpc', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(parsed)
                });
                const res = await resp.json();
                output.innerText = JSON.stringify(res, null, 2);
            } catch (e) {
                output.innerText = `Error: ${e.message}`;
            }
        }

        async function triggerRefresh() {
            const icon = document.getElementById('refreshIcon');
            icon.style.display = 'inline-block';
            icon.style.animation = 'spin 1s linear infinite';

            try {
                await fetch('/api/server/refresh', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });
                setTimeout(() => {
                    loadStatus();
                    performSearch(document.getElementById('searchInput').value);
                    icon.style.animation = '';
                }, 1000);
            } catch (e) {
                icon.style.animation = '';
            }
        }

        async function loadStatus() {
            try {
                const resp = await fetch('/api/status');
                if (!resp.ok) return;
                const data = await resp.json();

                document.getElementById('repoRootBadge').innerText = data.repo_root || 'Unknown';
                document.getElementById('repoRootBadge').title = data.repo_root || '';
                document.getElementById('tableRepoRoot').innerText = data.repo_root || '-';
                document.getElementById('tableWorkerRunning').innerText = data.worker_running ? 'Active (Running)' : 'Stopped';
                document.getElementById('tableRefreshInterval').innerText = `${data.interval_seconds || 30}s`;
                document.getElementById('statRefreshInterval').innerText = `${data.interval_seconds || 30}s`;
                document.getElementById('tableRefreshCount').innerText = data.refresh_count || '0';
                document.getElementById('tableSkippedCount').innerText = data.skipped_count || '0';

                const lastRef = data.last_refresh_at ? new Date(data.last_refresh_at).toLocaleTimeString() : 'Never';
                document.getElementById('tableLastRefresh').innerText = data.last_refresh_at || '-';
                document.getElementById('statLastRefresh').innerText = lastRef;

                // Symbols & files count from search
                const sResp = await fetch('/api/search?q=&limit=1');
                if (sResp.ok) {
                    const sData = await sResp.json();
                    document.getElementById('statSymbolsCount').innerText = sData.count || '0';
                }
            } catch (e) {
                console.error('Failed to load status', e);
            }
        }

        async function executeCallGraph(symbol) {
            const sym = symbol || document.getElementById('callGraphInput').value.trim();
            if (!sym) return;
            document.getElementById('callGraphInput').value = sym;
            document.getElementById('callGraphStatusBadge').innerText = `Analyzing ${sym}...`;

            try {
                const resp = await fetch(`/api/call-graph?symbol=${encodeURIComponent(sym)}`);
                if (!resp.ok) throw new Error('API error');
                const data = await resp.json();

                const targetCard = document.getElementById('callGraphTargetCard');
                if (data.definition) {
                    targetCard.style.display = 'block';
                    document.getElementById('cgTargetKind').innerText = data.definition.kind || 'SYMBOL';
                    document.getElementById('cgTargetName').innerText = data.definition.signature || data.definition.name;
                    document.getElementById('cgTargetLoc').innerText = `${data.definition.path}:${data.definition.line}`;
                    document.getElementById('cgTargetDoc').innerText = data.definition.doc_summary || 'No docstring';
                } else {
                    targetCard.style.display = 'block';
                    document.getElementById('cgTargetKind').innerText = 'SYMBOL';
                    document.getElementById('cgTargetName').innerText = sym;
                    document.getElementById('cgTargetLoc').innerText = 'External or undeclared';
                    document.getElementById('cgTargetDoc').innerText = 'References across codebase';
                }

                // Render Callers
                const callersList = document.getElementById('cgCallersList');
                callersList.innerHTML = '';
                document.getElementById('cgCallerCount').innerText = (data.callers || []).length;
                if (!data.callers || data.callers.length === 0) {
                    callersList.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem;">No incoming callers found in repository.</div>';
                } else {
                    data.callers.forEach(c => {
                        const item = document.createElement('div');
                        item.className = 'result-item';
                        item.innerHTML = `
                            <div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 0.2rem;">
                                <strong style="color: var(--accent-blue);">${escapeHtml(c.caller)}</strong>
                                <span style="color: var(--text-muted); font-family: var(--font-mono);">${escapeHtml(c.file)}:${c.line}</span>
                            </div>
                            <pre style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-secondary); margin: 0; background: rgba(0,0,0,0.3); padding: 0.3rem; border-radius: 4px; overflow-x: auto;"><code>${escapeHtml(c.snippet)}</code></pre>
                        `;
                        callersList.appendChild(item);
                    });
                }

                // Render Callees
                const calleesList = document.getElementById('cgCalleesList');
                calleesList.innerHTML = '';
                if (!data.callees || data.callees.length === 0) {
                    calleesList.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem;">No outgoing calls inside function body.</div>';
                } else {
                    data.callees.forEach(cl => {
                        const item = document.createElement('div');
                        item.style.cssText = 'padding: 0.35rem 0.6rem; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 4px; font-size: 0.85rem; cursor: pointer; display: flex; justify-content: space-between; align-items: center;';
                        item.innerHTML = `<span>➔ <strong>${escapeHtml(cl.name)}()</strong></span> <span style="color: var(--text-muted); font-size: 0.75rem;">${cl.target_file ? escapeHtml(cl.target_file) : ''}</span>`;
                        item.onclick = () => executeCallGraph(cl.name);
                        calleesList.appendChild(item);
                    });
                }

                // Render Imports
                const importsList = document.getElementById('cgImportsList');
                importsList.innerHTML = '';
                if (!data.imports || data.imports.length === 0) {
                    importsList.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem;">No imports found.</div>';
                } else {
                    data.imports.forEach(imp => {
                        const item = document.createElement('div');
                        item.style.cssText = 'padding: 0.25rem 0.5rem; background: var(--bg-card); border-radius: 4px; font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-secondary);';
                        item.innerText = imp;
                        importsList.appendChild(item);
                    });
                }

                document.getElementById('callGraphStatusBadge').innerText = `Found ${data.callers.length} references, ${data.callees.length} callees`;
            } catch (e) {
                document.getElementById('callGraphStatusBadge').innerText = `Error analyzing call graph: ${e.message}`;
            }
        }

        function escapeHtml(text) {
            if (!text) return '';
            return String(text)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        // Initialize on page load
        window.addEventListener('DOMContentLoaded', () => {
            setJsonRpcPayload('ping', {});
            loadStatus();
            performSearch();
        });
    </script>
</body>
</html>
"""
