/**
 * ZMQ AI Scalping EA - Ultra-low latency Expert Advisor
 * Connects to AI backend via ZeroMQ for real-time trading signals
 */

//--- Input parameters
input string SERVER_IP = "YOUR_ORACLE_CLOUD_IP";  // Oracle Cloud public IP
input int SIGNAL_PORT = 5555;
input int HEARTBEAT_PORT = 5556;
input double RISK_PERCENT = 0.02;        // Risk per trade (2%)
input double MAX_DAILY_LOSS = 0.05;      // Max daily loss (5%)
input double MIN_LOT_SIZE = 0.01;
input double MAX_LOT_SIZE = 1.0;
input int MAGIC_NUMBER = 12345;
input int MAX_TRADES_PER_SYMBOL = 3;
input double ATR_SL_MULTIPLIER = 1.5;
input int HEARTBEAT_INTERVAL = 60;       // Seconds

//--- Global variables
int zmq_context;
int zmq_subscriber;
int zmq_requester;
datetime last_heartbeat = 0;
double daily_pnl = 0.0;
double daily_start_balance = 0.0;
int trade_count = 0;

//--- Chart display variables
string chart_info = "";
long last_signal_time = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    Print("=== ZMQ AI Scalping EA v1.0.0 ===");

    // Initialize ZMQ
    if (!InitializeZMQ()) {
        Print("Failed to initialize ZMQ. EA will not work.");
        return INIT_FAILED;
    }

    // Initialize chart display
    InitializeChartDisplay();

    // Set daily start balance
    daily_start_balance = AccountBalance();

    Print("ZMQ EA initialized successfully. Waiting for AI signals...");
    Print(StringFormat("Server: %s:%d", SERVER_IP, SIGNAL_PORT));

    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Print("Deinitializing ZMQ EA...");

    // Close ZMQ connections
    if (zmq_subscriber != 0) {
        ZMQ::zmq_close(zmq_subscriber);
        zmq_subscriber = 0;
    }
    if (zmq_requester != 0) {
        ZMQ::zmq_close(zmq_requester);
        zmq_requester = 0;
    }
    if (zmq_context != 0) {
        ZMQ::zmq_ctx_destroy(zmq_context);
        zmq_context = 0;
    }

    Print("ZMQ EA deinitialized.");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
    // Update chart display
    UpdateChartDisplay();

    // Check for new signals (non-blocking)
    CheckForSignals();

    // Send heartbeat
    if (TimeCurrent() - last_heartbeat >= HEARTBEAT_INTERVAL) {
        SendHeartbeat();
        last_heartbeat = TimeCurrent();
    }

    // Check circuit breaker
    if (GetDailyPnL() <= -MAX_DAILY_LOSS) {
        Print("CIRCUIT BREAKER: Daily loss limit reached. Stopping trading.");
        ExpertRemove();
        return;
    }
}

//+------------------------------------------------------------------+
//| Initialize ZMQ connections                                       |
//+------------------------------------------------------------------+
bool InitializeZMQ()
{
    // Create ZMQ context
    zmq_context = ZMQ::zmq_ctx_new();
    if (zmq_context == 0) {
        Print("Failed to create ZMQ context");
        return false;
    }

    // Create subscriber socket for signals
    zmq_subscriber = ZMQ::zmq_socket(zmq_context, ZMQ_SUB);
    if (zmq_subscriber == 0) {
        Print("Failed to create subscriber socket");
        return false;
    }

    // Create requester socket for heartbeat
    zmq_requester = ZMQ::zmq_socket(zmq_context, ZMQ_REQ);
    if (zmq_requester == 0) {
        Print("Failed to create requester socket");
        return false;
    }

    // Connect subscriber
    string signal_address = StringFormat("tcp://%s:%d", SERVER_IP, SIGNAL_PORT);
    if (ZMQ::zmq_connect(zmq_subscriber, signal_address) != 0) {
        Print("Failed to connect subscriber to ", signal_address);
        return false;
    }

    // Subscribe to all topics
    if (ZMQ::zmq_setsockopt(zmq_subscriber, ZMQ_SUBSCRIBE, "", 0) != 0) {
        Print("Failed to set subscriber options");
        return false;
    }

    // Connect requester
    string heartbeat_address = StringFormat("tcp://%s:%d", SERVER_IP, HEARTBEAT_PORT);
    if (ZMQ::zmq_connect(zmq_requester, heartbeat_address) != 0) {
        Print("Failed to connect requester to ", heartbeat_address);
        return false;
    }

    Print("ZMQ connections established successfully");
    return true;
}

//+------------------------------------------------------------------+
//| Check for new trading signals                                    |
//+------------------------------------------------------------------+
void CheckForSignals()
{
    if (zmq_subscriber == 0) return;

    // Non-blocking receive
    uchar buffer[];
    int result = ZMQ::zmq_recv(zmq_subscriber, buffer, ZMQ_DONTWAIT);

    if (result > 0) {
        // Convert buffer to string
        string message = CharArrayToString(buffer, 0, result);

        // Parse JSON signal
        if (ProcessSignal(message)) {
            last_signal_time = GetTickCount();
        }
    }
}

//+------------------------------------------------------------------+
//| Process incoming trading signal                                  |
//+------------------------------------------------------------------+
bool ProcessSignal(string message)
{
    // Parse JSON (simplified - in production use proper JSON parser)
    string symbol = ExtractValue(message, "symbol");
    string action = ExtractValue(message, "action");
    string confidence_str = ExtractValue(message, "confidence");
    string reason = ExtractValue(message, "reason");

    if (symbol == "" || action == "") {
        Print("Invalid signal format: ", message);
        return false;
    }

    double confidence = StringToDouble(confidence_str);

    // Log signal
    Print(StringFormat("AI Signal: %s %s (%.1f%%) - %s",
          action, symbol, confidence * 100, reason));

    // Validate signal
    if (!ValidateSignal(symbol, action, confidence)) {
        Print("Signal validation failed");
        return false;
    }

    // Execute trade
    if (ExecuteTrade(symbol, action, confidence, reason)) {
        trade_count++;
        return true;
    }

    return false;
}

//+------------------------------------------------------------------+
//| Validate trading signal                                          |
//+------------------------------------------------------------------+
bool ValidateSignal(string symbol, string action, double confidence)
{
    // Check confidence threshold
    if (confidence < 0.75) {
        Print("Signal rejected: Low confidence (", confidence, ")");
        return false;
    }

    // Check symbol
    if (Symbol() != symbol) {
        // Signal for different symbol - could implement multi-symbol trading
        return false;
    }

    // Check spread
    double spread = Ask - Bid;
    double max_spread = GetMaxSpread(symbol);
    if (spread > max_spread) {
        Print("Signal rejected: Spread too wide (", spread, " > ", max_spread, ")");
        return false;
    }

    // Check volatility (ATR-based)
    double atr = iATR(symbol, PERIOD_M1, 14, 0);
    if (atr < 0.0005) {
        Print("Signal rejected: Low volatility (ATR = ", atr, ")");
        return false;
    }

    // Check existing positions
    if (CountOpenTrades(symbol) >= MAX_TRADES_PER_SYMBOL) {
        Print("Signal rejected: Max positions reached for ", symbol);
        return false;
    }

    // Check daily loss limit
    if (GetDailyPnL() <= -MAX_DAILY_LOSS) {
        Print("Signal rejected: Daily loss limit reached");
        return false;
    }

    return true;
}

//+------------------------------------------------------------------+
//| Execute trading signal                                           |
//+------------------------------------------------------------------+
bool ExecuteTrade(string symbol, string action, double confidence, string reason)
{
    // Calculate position size
    double lot_size = CalculatePositionSize(symbol, confidence);

    // Calculate stop loss and take profit
    double sl_distance = CalculateSL(symbol);
    double tp_levels[3];
    CalculateTP(symbol, sl_distance, tp_levels);

    // Determine order type
    int order_type = (action == "BUY") ? OP_BUY : OP_SELL;
    double entry_price = (order_type == OP_BUY) ? Ask : Bid;

    // Calculate SL and TP prices
    double sl_price = (order_type == OP_BUY) ?
        entry_price - sl_distance : entry_price + sl_distance;
    double tp_price = (order_type == OP_BUY) ?
        entry_price + tp_levels[0] : entry_price - tp_levels[0];

    // Submit order
    int ticket = OrderSend(
        symbol,
        order_type,
        lot_size,
        entry_price,
        3,  // Max slippage (3 pips)
        sl_price,
        tp_price,
        StringFormat("AI-%.0f%% [%s]", confidence * 100, reason),
        MAGIC_NUMBER,
        0,
        (order_type == OP_BUY) ? clrGreen : clrRed
    );

    if (ticket > 0) {
        Print(StringFormat("Trade executed: #%d %s %s %.2f lots @ %.5f SL:%.5f TP:%.5f",
              ticket, action, symbol, lot_size, entry_price, sl_price, tp_price));

        // Annotate chart
        AnnotateTrade(ticket, action, entry_price, sl_price, tp_price);

        // Enable trailing stop
        StartTrailingStop(ticket, sl_distance * 0.5);

        return true;
    } else {
        int error = GetLastError();
        Print(StringFormat("Trade failed: %s (Error: %d)", ErrorDescription(error), error));
        return false;
    }
}

//+------------------------------------------------------------------+
//| Calculate position size using Kelly Criterion                    |
//+------------------------------------------------------------------+
double CalculatePositionSize(string symbol, double confidence)
{
    double account_balance = AccountBalance();
    double risk_amount = account_balance * RISK_PERCENT;

    // Kelly Criterion adjustment
    double win_rate = GetWinRate();  // From recent trades
    double kelly_factor = (confidence * win_rate - (1 - win_rate)) / win_rate;
    kelly_factor = MathMax(0, MathMin(kelly_factor, 0.5));  // Cap at 50% Kelly

    // Adjust for volatility
    double atr = iATR(symbol, PERIOD_M1, 14, 0);
    double base_volatility = 0.001;  // Base volatility for EURUSD
    double volatility_multiplier = base_volatility / atr;

    // Calculate lot size
    double sl_distance = CalculateSL(symbol);
    double tick_value = MarketInfo(symbol, MODE_TICKVALUE);
    double lot_size = (risk_amount * kelly_factor) / (sl_distance * tick_value);

    // Apply limits
    lot_size = MathMax(MIN_LOT_SIZE, MathMin(lot_size, MAX_LOT_SIZE));

    return NormalizeDouble(lot_size, 2);
}

//+------------------------------------------------------------------+
//| Calculate stop loss distance                                     |
//+------------------------------------------------------------------+
double CalculateSL(string symbol)
{
    double atr = iATR(symbol, PERIOD_M1, 14, 0);
    return atr * ATR_SL_MULTIPLIER;
}

//+------------------------------------------------------------------+
//| Calculate take profit levels (multi-level)                       |
//+------------------------------------------------------------------+
void CalculateTP(string symbol, double sl_distance, double &tp_levels[])
{
    // First TP: 1.5R (1.5:1 reward-to-risk)
    tp_levels[0] = sl_distance * 1.5;
    // Second TP: 3R (3:1 reward-to-risk)
    tp_levels[1] = sl_distance * 3.0;
    // Final TP: 5R (5:1 reward-to-risk)
    tp_levels[2] = sl_distance * 5.0;
}

//+------------------------------------------------------------------+
//| Send heartbeat to server                                         |
//+------------------------------------------------------------------+
void SendHeartbeat()
{
    if (zmq_requester == 0) return;

    // Prepare heartbeat message
    string heartbeat_msg = StringFormat(
        "{\"type\":\"heartbeat\",\"client_timestamp\":%lld,\"account_balance\":%.2f,\"daily_pnl\":%.2f,\"open_trades\":%d}",
        GetTickCount() * 1000000,  // Convert to nanoseconds
        AccountBalance(),
        GetDailyPnL(),
        CountOpenTrades()
    );

    // Convert to char array
    uchar msg_buffer[];
    StringToCharArray(heartbeat_msg, msg_buffer);

    // Send heartbeat
    if (ZMQ::zmq_send(zmq_requester, msg_buffer, ZMQ_DONTWAIT) > 0) {
        // Receive response (non-blocking)
        uchar resp_buffer[];
        int resp_result = ZMQ::zmq_recv(zmq_requester, resp_buffer, ZMQ_DONTWAIT);

        if (resp_result > 0) {
            string response = CharArrayToString(resp_buffer, 0, resp_result);
            // Parse response if needed
            // Print("Heartbeat response: ", response);
        }
    }
}

//+------------------------------------------------------------------+
//| Manage partial exits and trailing stops                          |
//+------------------------------------------------------------------+
void ManageTrades()
{
    for (int i = OrdersTotal() - 1; i >= 0; i--) {
        if (OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) {
            if (OrderMagicNumber() == MAGIC_NUMBER && OrderSymbol() == Symbol()) {
                ManagePartialExits(OrderTicket());
                UpdateTrailingStop(OrderTicket());
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Manage partial profit taking                                     |
//+------------------------------------------------------------------+
void ManagePartialExits(int ticket)
{
    if (!OrderSelect(ticket, SELECT_BY_TICKET)) return;

    double open_price = OrderOpenPrice();
    double current_price = (OrderType() == OP_BUY) ? Bid : Ask;
    double profit_pips = MathAbs(current_price - open_price) / Point;

    double sl_distance = MathAbs(OrderStopLoss() - open_price) / Point;
    double tp_distance = MathAbs(OrderTakeProfit() - open_price) / Point;

    // Close 50% at 50% of TP
    if (profit_pips >= tp_distance * 0.5 && !IsPartialClosed(ticket, 1)) {
        ClosePartial(ticket, 0.5, "TP1-50%");
        SetBreakeven(ticket);
    }

    // Close 30% at 80% of TP
    if (profit_pips >= tp_distance * 0.8 && !IsPartialClosed(ticket, 2)) {
        ClosePartial(ticket, 0.3, "TP2-80%");
    }
}

//+------------------------------------------------------------------+
//| Update trailing stop                                             |
//+------------------------------------------------------------------+
void UpdateTrailingStop(int ticket, double trail_distance = 0)
{
    if (!OrderSelect(ticket, SELECT_BY_TICKET)) return;

    if (trail_distance == 0) {
        double atr = iATR(OrderSymbol(), PERIOD_M1, 14, 0);
        trail_distance = atr * 0.5;  // Trail at 0.5 ATR
    }

    double current_price = (OrderType() == OP_BUY) ? Bid : Ask;
    double new_sl = 0;

    if (OrderType() == OP_BUY) {
        new_sl = current_price - trail_distance;
        if (new_sl > OrderStopLoss()) {
            OrderModify(ticket, OrderOpenPrice(), new_sl, OrderTakeProfit(), 0);
        }
    } else {
        new_sl = current_price + trail_distance;
        if (new_sl < OrderStopLoss()) {
            OrderModify(ticket, OrderOpenPrice(), new_sl, OrderTakeProfit(), 0);
        }
    }
}

//+------------------------------------------------------------------+
//| Utility functions                                                |
//+------------------------------------------------------------------+
double GetDailyPnL()
{
    return AccountBalance() - daily_start_balance;
}

double GetWinRate()
{
    // Simplified - in production calculate from trade history
    return 0.55;  // Assume 55% win rate
}

int CountOpenTrades(string symbol = "")
{
    int count = 0;
    for (int i = 0; i < OrdersTotal(); i++) {
        if (OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) {
            if (OrderMagicNumber() == MAGIC_NUMBER) {
                if (symbol == "" || OrderSymbol() == symbol) {
                    count++;
                }
            }
        }
    }
    return count;
}

double GetMaxSpread(string symbol)
{
    // Return max acceptable spread in points
    if (StringFind(symbol, "EURUSD") >= 0) return 2.0;
    if (StringFind(symbol, "GBPUSD") >= 0) return 3.0;
    if (StringFind(symbol, "BTCUSD") >= 0) return 50.0;
    return 5.0;  // Default
}

string ExtractValue(string json, string key)
{
    // Very basic JSON parser - in production use proper JSON library
    string search = "\"" + key + "\":";
    int start = StringFind(json, search);
    if (start < 0) return "";

    start += StringLen(search);
    int end = StringFind(json, ",", start);
    if (end < 0) end = StringFind(json, "}", start);
    if (end < 0) return "";

    string value = StringSubstr(json, start, end - start);
    StringTrimLeft(value);
    StringTrimRight(value);

    // Remove quotes if present
    if (StringGetCharacter(value, 0) == '"') {
        value = StringSubstr(value, 1, StringLen(value) - 2);
    }

    return value;
}

void ClosePartial(int ticket, double percent, string comment)
{
    if (!OrderSelect(ticket, SELECT_BY_TICKET)) return;

    double close_lots = OrderLots() * percent;
    double close_price = (OrderType() == OP_BUY) ? Bid : Ask;

    int close_ticket = OrderClose(ticket, close_lots, close_price, 3, clrBlue);
    if (close_ticket > 0) {
        Print(StringFormat("Partial close: #%d %.2f lots (%s)", ticket, close_lots, comment));
    }
}

bool IsPartialClosed(int ticket, int level)
{
    // Simplified - in production track partial closes
    return false;
}

void SetBreakeven(int ticket)
{
    if (!OrderSelect(ticket, SELECT_BY_TICKET)) return;

    double open_price = OrderOpenPrice();
    double spread = Ask - Bid;

    if (OrderType() == OP_BUY) {
        double be_price = open_price + spread;
        if (Bid > be_price && OrderStopLoss() < be_price) {
            OrderModify(ticket, open_price, be_price, OrderTakeProfit(), 0);
        }
    } else {
        double be_price = open_price - spread;
        if (Ask < be_price && OrderStopLoss() > be_price) {
            OrderModify(ticket, open_price, be_price, OrderTakeProfit(), 0);
        }
    }
}

void StartTrailingStop(int ticket, double trail_distance)
{
    // Set initial trailing stop
    UpdateTrailingStop(ticket, trail_distance);
}

//+------------------------------------------------------------------+
//| Chart display functions                                          |
//+------------------------------------------------------------------+
void InitializeChartDisplay()
{
    // Create chart objects for display
    if (ObjectCreate("AI_Status", OBJ_LABEL, 0, 0, 0)) {
        ObjectSet("AI_Status", OBJPROP_CORNER, CORNER_LEFT_UPPER);
        ObjectSet("AI_Status", OBJPROP_XDISTANCE, 10);
        ObjectSet("AI_Status", OBJPROP_YDISTANCE, 10);
    }
}

void UpdateChartDisplay()
{
    string status = StringFormat(
        "AI Scalping EA Active\\n" +
        "Balance: $%.2f\\n" +
        "Daily P&L: $%.2f\\n" +
        "Open Trades: %d\\n" +
        "Last Signal: %s ago\\n" +
        "Server: %s:%d",
        AccountBalance(),
        GetDailyPnL(),
        CountOpenTrades(),
        last_signal_time > 0 ? TimeToString(TimeCurrent() - last_signal_time, TIME_SECONDS) : "Never",
        SERVER_IP,
        SIGNAL_PORT
    );

    if (ObjectFind("AI_Status") >= 0) {
        ObjectSetText("AI_Status", status, 8, "Arial", clrWhite);
    }

    // Update main chart comment
    Comment(status);
}

void AnnotateTrade(int ticket, string action, double entry, double sl, double tp)
{
    // Create chart annotation for the trade
    string obj_name = StringFormat("Trade_%d", ticket);

    if (action == "BUY") {
        // Draw buy arrow
        if (ObjectCreate(obj_name, OBJ_ARROW_BUY, 0, TimeCurrent(), entry)) {
            ObjectSet(obj_name, OBJPROP_COLOR, clrGreen);
            ObjectSet(obj_name, OBJPROP_WIDTH, 2);
        }
    } else {
        // Draw sell arrow
        if (ObjectCreate(obj_name, OBJ_ARROW_SELL, 0, TimeCurrent(), entry)) {
            ObjectSet(obj_name, OBJPROP_COLOR, clrRed);
            ObjectSet(obj_name, OBJPROP_WIDTH, 2);
        }
    }

    // Draw SL line
    string sl_name = StringFormat("SL_%d", ticket);
    if (ObjectCreate(sl_name, OBJ_HLINE, 0, 0, sl)) {
        ObjectSet(sl_name, OBJPROP_COLOR, clrRed);
        ObjectSet(sl_name, OBJPROP_STYLE, STYLE_DASH);
    }

    // Draw TP line
    string tp_name = StringFormat("TP_%d", ticket);
    if (ObjectCreate(tp_name, OBJ_HLINE, 0, 0, tp)) {
        ObjectSet(tp_name, OBJPROP_COLOR, clrGreen);
        ObjectSet(tp_name, OBJPROP_STYLE, STYLE_DASH);
    }
}

//+------------------------------------------------------------------+
//| Error handling                                                   |
//+------------------------------------------------------------------+
string ErrorDescription(int error_code)
{
    switch(error_code) {
        case 0: return "No error";
        case 1: return "No error, trade was executed";
        case 2: return "Common error";
        case 3: return "Invalid trade parameters";
        case 4: return "Trade server is busy";
        case 5: return "Old version of the client terminal";
        case 6: return "No connection with trade server";
        case 7: return "Not enough rights";
        case 8: return "Too frequent requests";
        case 9: return "Malfunctional trade operation";
        case 64: return "Account disabled";
        case 65: return "Invalid account";
        case 128: return "Trade timeout";
        case 129: return "Invalid price";
        case 130: return "Invalid stops";
        case 131: return "Invalid trade volume";
        case 132: return "Market is closed";
        case 133: return "Trade is disabled";
        case 134: return "Not enough money";
        case 135: return "Price changed";
        case 136: return "Off quotes";
        case 137: return "Broker is busy";
        case 138: return "Requote";
        case 139: return "Order is locked";
        case 140: return "Long positions only allowed";
        case 141: return "Too many requests";
        case 142: return "Trade context is busy";
        case 143: return "Trade expiration denied";
        case 144: return "Only Buy orders allowed";
        case 145: return "Only Sell orders allowed";
        case 146: return "Only Buy Limit orders allowed";
        case 147: return "Only Sell Limit orders allowed";
        case 148: return "Only Buy Stop orders allowed";
        case 149: return "Only Sell Stop orders allowed";
        case 4000: return "No error";
        case 4001: return "Wrong function pointer";
        case 4002: return "Array index is out of range";
        case 4003: return "No memory for function call stack";
        case 4004: return "Recursive stack overflow";
        case 4005: return "Not enough stack for parameter";
        case 4006: return "No memory for parameter string";
        case 4007: return "No memory for temp string";
        case 4008: return "Not initialized string";
        case 4009: return "Not initialized string in array";
        case 4010: return "No memory for array string";
        case 4011: return "Too long string";
        case 4012: return "Remainder from division by zero";
        case 4013: return "Zero divide";
        case 4014: return "Unknown command";
        case 4015: return "Wrong jump (never generated error)";
        case 4016: return "Not initialized array";
        case 4017: return "DLL calls are not allowed";
        case 4018: return "Cannot load library";
        case 4019: return "Cannot call function";
        case 4020: return "External calls are not allowed";
        case 4021: return "No memory for returned string";
        case 4022: return "System is busy";
        case 4023: return "DLL-function call critical error";
        case 4024: return "Internal error";
        case 4025: return "Out of memory";
        case 4026: return "Invalid pointer";
        case 4027: return "Too many formatters in the format function";
        case 4028: return "Parameters count is more than formatters";
        case 4029: return "Invalid array";
        case 4030: return "No reply from chart";
        default: return StringFormat("Unknown error (%d)", error_code);
    }
}
//+------------------------------------------------------------------+