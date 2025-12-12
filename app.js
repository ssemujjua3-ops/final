class TradingBotApp {
    constructor() {
        this.updateInterval = null;
        this.chartData = null;
        this.currentSignal = { direction: 'HOLD', confidence: 0.5 };
        this.init();
    }

    init() {
        this.bindEvents();
        this.initChart();
        this.startUpdates();
    }

    bindEvents() {
        document.getElementById('btn-start').addEventListener('click', () => this.sendAction('start'));
        document.getElementById('btn-stop').addEventListener('click', () => this.sendAction('stop'));
        document.getElementById('btn-trade').addEventListener('click', () => this.sendAction('start_trading'));
        document.getElementById('btn-stop-trade').addEventListener('click', () => this.sendAction('stop_trading'));
        
        document.getElementById('asset-select').addEventListener('change', (e) => {
            this.sendAction('set_asset', e.target.value);
        });
        
        document.getElementById('timeframe-select').addEventListener('change', (e) => {
            this.sendAction('set_timeframe', e.target.value);
        });
        
        const slider = document.getElementById('confidence-slider');
        slider.addEventListener('input', (e) => {
            document.getElementById('confidence-value').textContent = e.target.value + '%';
        });
        slider.addEventListener('change', (e) => {
            this.sendAction('set_confidence', e.target.value / 100);
        });

        document.getElementById('btn-upload-pdf').addEventListener('click', () => this.uploadPDF());
    }

    startUpdates() {
        // Initial fetch
        this.fetchData();
        // Set interval to update every 3 seconds
        this.updateInterval = setInterval(() => this.fetchData(), 3000);
    }

    async fetchData() {
        try {
            const [statusResponse, analysisResponse, tradeResponse] = await Promise.all([
                fetch('/status').then(res => res.json()),
                fetch('/market-analysis').then(res => res.json()),
                fetch('/trade-stats').then(res => res.json())
            ]);
            
            this.updateStatus(statusResponse);
            this.updateStats(statusResponse, tradeResponse);
            this.updateAnalysis(analysisResponse);
            this.updateChart(analysisResponse);
            this.updateTrades(tradeResponse);
            
            // Temporary Signal Logic (should come from a dedicated endpoint/field in status in a real app)
            // For now, let's use the pattern analysis to generate a visual signal
            this.updateSignal(analysisResponse);

        } catch (error) {
            console.error("Error fetching data:", error);
            document.getElementById('status-connection').textContent = 'SERVER ERROR';
            document.getElementById('status-connection').className = 'status-indicator status-off';
        }
    }

    async sendAction(action, value = null) {
        try {
            const response = await fetch('/action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: action, value: value })
            });
            const data = await response.json();
            console.log(`Action ${action} response:`, data);
            
            if (data.status === 'error') {
                alert(`Action Failed: ${data.message}`);
            }

            // Immediately fetch new status after an action
            this.fetchData();
        } catch (error) {
            console.error(`Error sending action ${action}:`, error);
        }
    }

    async uploadPDF() {
        const fileInput = document.getElementById('pdf-file-input');
        if (fileInput.files.length === 0) {
            alert("Please select a PDF file first.");
            return;
        }

        const formData = new FormData();
        formData.append('pdf', fileInput.files[0]);

        document.getElementById('btn-upload-pdf').textContent = "Learning...";
        document.getElementById('btn-upload-pdf').disabled = true;

        try {
            const response = await fetch('/upload-pdf', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            alert(data.message);
        } catch (error) {
            alert("Upload failed. See console for details.");
            console.error("Upload Error:", error);
        } finally {
            document.getElementById('btn-upload-pdf').textContent = "UPLOAD & LEARN";
            document.getElementById('btn-upload-pdf').disabled = false;
        }
        this.fetchData();
    }

    updateStatus(status) {
        const isRunning = status.is_running;
        const isTrading = status.is_trading;
        const isConnected = status.connected;

        // Connection Status
        const connStatus = document.getElementById('status-connection');
        connStatus.textContent = isConnected ? 'CONNECTED' : 'DISCONNECTED';
        connStatus.className = `status-indicator status-${isConnected ? 'on' : 'off'}`;

        // Trading Status
        const tradeStatus = document.getElementById('status-trading');
        tradeStatus.textContent = isTrading ? 'TRADING ON' : 'TRADING OFF';
        tradeStatus.className = `status-indicator status-${isTrading ? 'on' : 'neutral'}`;

        // Mode Status
        const modeStatus = document.getElementById('status-mode');
        modeStatus.textContent = `MODE: ${status.simulation_mode ? 'SIMULATION' : 'REAL'}`;
        modeStatus.className = `status-indicator status-${status.simulation_mode ? 'neutral' : 'on'}`;

        // Button states
        document.getElementById('btn-start').disabled = isRunning;
        document.getElementById('btn-stop').disabled = !isRunning;
        document.getElementById('btn-trade').disabled = !isRunning || isTrading;
        document.getElementById('btn-stop-trade').disabled = !isRunning || !isTrading;

        // Set current asset/timeframe in dropdowns
        document.getElementById('asset-select').value = status.current_asset;
        document.getElementById('timeframe-select').value = status.current_timeframe;
    }

    updateStats(status, trades) {
        const balance = status.balance.toFixed(2);
        const winRate = (trades.win_rate * 100).toFixed(2);
        
        document.getElementById('stat-balance').textContent = `$${balance}`;
        document.getElementById('stat-total-trades').textContent = trades.total;
        document.getElementById('stat-win-rate').textContent = `${winRate}%`;
        document.getElementById('stat-wins-losses').textContent = `${trades.wins} / ${trades.losses}`;
        document.getElementById('stat-trades-hour').textContent = status.trades_this_hour;
        
        document.getElementById('stat-ml-win-rate').textContent = `${(status.agent_stats.win_rate * 100).toFixed(2)}%`;
        document.getElementById('concepts-learned').textContent = status.knowledge_stats.total_concepts;
    }

    updateAnalysis(analysis) {
        document.getElementById('analysis-trend').textContent = analysis.trend.toUpperCase();
        document.getElementById('analysis-patterns').textContent = analysis.patterns.length;

        // Nearest levels
        const res = analysis.levels.resistance[0];
        const sup = analysis.levels.support[0];

        document.getElementById('analysis-resistance').textContent = res ? `$${res.price.toFixed(5)}` : 'N/A';
        document.getElementById('analysis-support').textContent = sup ? `$${sup.price.toFixed(5)}` : 'N/A';
    }

    updateSignal(analysis) {
        // Simplified Signal Logic: If any strong pattern or trend is detected, generate a placeholder signal.
        const trend = analysis.trend;
        const patterns = analysis.patterns;
        
        let call_score = 0;
        let put_score = 0;

        // Score based on trend
        if (trend === 'uptrend') call_score += 1;
        if (trend === 'downtrend') put_score += 1;

        // Score based on patterns
        patterns.forEach(p => {
            if (p.signal === 'CALL') call_score += p.strength * 1.5;
            if (p.signal === 'PUT') put_score += p.strength * 1.5;
        });

        const total = call_score + put_score;
        let direction = 'HOLD';
        let confidence = 0.5;
        let reasoning = "Waiting for strong signal...";

        if (total > 1.5) { // Need a minimum accumulated score
            if (call_score > put_score) {
                direction = 'CALL';
                confidence = Math.min(call_score / total, 0.9);
                reasoning = `Strong Bullish signs: Trend (${trend}) + ${patterns.length} Bullish Pattern(s).`;
            } else if (put_score > call_score) {
                direction = 'PUT';
                confidence = Math.min(put_score / total, 0.9);
                reasoning = `Strong Bearish signs: Trend (${trend}) + ${patterns.length} Bearish Pattern(s).`;
            }
        }
        
        const confidencePct = (confidence * 100).toFixed(0);

        const signalDirectionEl = document.getElementById('signal-direction');
        signalDirectionEl.textContent = direction;
        signalDirectionEl.className = `signal-direction ${direction.toLowerCase()}`;
        document.getElementById('signal-confidence').textContent = `${confidencePct}%`;
        document.getElementById('signal-reasoning').textContent = reasoning;
    }

    updateTrades(tradeStats) {
        const body = document.getElementById('trades-list-body');
        body.innerHTML = '';
        
        if (tradeStats.history.length === 0) {
            body.innerHTML = '<tr><td colspan="5" class="no-data">No trades executed yet.</td></tr>';
            return;
        }

        tradeStats.history.forEach(trade => {
            const row = body.insertRow();
            
            const time = new Date(trade.created_at).toLocaleTimeString();
            const outcomeClass = trade.outcome ? `trade-${trade.outcome.toLowerCase()}` : 'trade-pending';
            
            row.insertCell().textContent = time;
            row.insertCell().textContent = trade.asset;
            row.insertCell().textContent = trade.direction;
            row.insertCell().textContent = trade.amount.toFixed(2);
            
            const outcomeCell = row.insertCell();
            outcomeCell.textContent = trade.outcome || 'PENDING';
            outcomeCell.className = outcomeClass;
        });
    }

    initChart() {
        const layout = {
            title: 'Candlestick Chart',
            dragmode: 'zoom',
            showlegend: false,
            autosize: true,
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0.2)',
            font: { color: '#e4e4e4' },
            margin: { t: 30, r: 30, b: 30, l: 50 },
            xaxis: { 
                showgrid: false, 
                color: '#666',
                rangeslider: { visible: false } // Hide the rangeslider at the bottom
            },
            yaxis: { 
                showgrid: true, 
                gridcolor: 'rgba(255,255,255,0.1)', 
                color: '#666' 
            }
        };

        // Create an empty chart initially
        Plotly.newPlot('market-chart', [], layout, { responsive: true, displayModeBar: false });
    }

    updateChart(analysis) {
        if (!analysis.candles || analysis.candles.length === 0) return;

        // Plotly expects oldest-to-newest, but the API returns newest-to-oldest.
        // We reverse it, and only take the last 50 for a clean view.
        const candles = analysis.candles.slice(0, 50).reverse();
        
        const trace = {
            x: candles.map((_, i) => i), // Use index for x-axis simplicity
            open: candles.map(c => c.open),
            high: candles.map(c => c.high),
            low: candles.map(c => c.low),
            close: candles.map(c => c.close),
            type: 'candlestick',
            name: 'Candles',
            increasing: { line: { color: '#00ff88' }, fillcolor: '#00ff88' },
            decreasing: { line: { color: '#ff4444' }, fillcolor: '#ff4444' }
        };

        // Update the chart data
        Plotly.react('market-chart', [trace], {
            // Layout properties for react update
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0.2)',
            font: { color: '#e4e4e4' },
            margin: { t: 30, r: 30, b: 30, l: 50 },
            xaxis: { 
                showgrid: false, 
                color: '#666',
                rangeslider: { visible: false }
            },
            yaxis: { 
                showgrid: true, 
                gridcolor: 'rgba(255,255,255,0.1)', 
                color: '#666' 
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new TradingBotApp();
});
