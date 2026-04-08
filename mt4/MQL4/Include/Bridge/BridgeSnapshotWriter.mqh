// MQL4/Include/Bridge/BridgeSnapshotWriter.mqh
#ifndef __BRIDGE_SNAPSHOT_WRITER_MQH__
#define __BRIDGE_SNAPSHOT_WRITER_MQH__

#include <Bridge/BridgeConfig.mqh>
#include <Bridge/BridgeUtils.mqh>
#include <Bridge/BridgeFileIO.mqh>

string BridgeBuildMarketSnapshotJson(const BridgeSettings &settings, MqlRates &rates[], int copied)
{
    int digits = (int)MarketInfo(settings.target_symbol, MODE_DIGITS);
    double point = MarketInfo(settings.target_symbol, MODE_POINT);
    int spread_points = (int)MarketInfo(settings.target_symbol, MODE_SPREAD);
    datetime last_tick_time = (datetime)MarketInfo(settings.target_symbol, MODE_TIME);

    string json = "{";
    json += "\"schema_version\":\"1.0\",";
    json += "\"generated_at\":" + BridgeJsonDateTime(TimeCurrent()) + ",";
    json += "\"symbol\":" + BridgeJsonString(settings.target_symbol) + ",";
    json += "\"timeframe\":" + BridgeJsonString(BridgeTimeframeToString(settings.bars_timeframe)) + ",";
    json += "\"bars_requested\":" + BridgeJsonInt(settings.bars_to_export) + ",";
    json += "\"bars_copied\":" + BridgeJsonInt(copied) + ",";
    json += "\"bid\":" + BridgeJsonDouble(Bid, digits) + ",";
    json += "\"ask\":" + BridgeJsonDouble(Ask, digits) + ",";
    json += "\"spread_points\":" + BridgeJsonInt(spread_points) + ",";
    json += "\"digits\":" + BridgeJsonInt(digits) + ",";
    json += "\"point\":" + BridgeJsonDouble(point, digits) + ",";
    json += "\"last_tick_time\":" + BridgeJsonDateTime(last_tick_time) + ",";
    json += "\"bars\":" + BridgeBuildJsonBars(rates, copied, digits);
    json += "}";

    return json;
}

string BridgeBuildRuntimeStatusJson(const BridgeSettings &settings, const string mode, const string detail)
{
    datetime last_tick_time = (datetime)MarketInfo(settings.target_symbol, MODE_TIME);

    string json = "{";
    json += "\"schema_version\":\"1.0\",";
    json += "\"updated_at\":" + BridgeJsonDateTime(TimeCurrent()) + ",";
    json += "\"ea_name\":" + BridgeJsonString(settings.ea_name) + ",";
    json += "\"ea_version\":" + BridgeJsonString(settings.ea_version) + ",";
    json += "\"symbol\":" + BridgeJsonString(settings.target_symbol) + ",";
    json += "\"terminal_connected\":" + BridgeJsonBool(IsConnected()) + ",";
    json += "\"trade_allowed\":" + BridgeJsonBool(IsTradeAllowed()) + ",";
    json += "\"use_common_files\":" + BridgeJsonBool(settings.use_common_files) + ",";
    json += "\"bridge_root\":" + BridgeJsonString(settings.root_path) + ",";
    json += "\"timeframe\":" + BridgeJsonString(BridgeTimeframeToString(settings.bars_timeframe)) + ",";
    json += "\"last_tick_time\":" + BridgeJsonDateTime(last_tick_time) + ",";
    json += "\"mode\":" + BridgeJsonString(mode) + ",";
    json += "\"detail\":" + BridgeJsonString(detail);
    json += "}";

    return json;
}

string BridgeBuildPositionSnapshotJson(const BridgeSettings &settings)
{
    string json = "{";
    json += "\"schema_version\":\"1.0\",";
    json += "\"generated_at\":" + BridgeJsonDateTime(TimeCurrent()) + ",";
    json += "\"positions\":[";
    bool first = true;

    for(int i = OrdersTotal() - 1; i >= 0; i--)
    {
        if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
        {
            continue;
        }

        if(OrderSymbol() != settings.target_symbol)
        {
            continue;
        }

        if(!BridgeIsManagedMagicNumber(settings, OrderMagicNumber()))
        {
            continue;
        }

        int order_type = OrderType();
        if(order_type != OP_BUY && order_type != OP_SELL)
        {
            continue;
        }

        if(!first)
        {
            json += ",";
        }
        first = false;

        string position_type = (order_type == OP_BUY) ? "buy" : "sell";

        json += "{";
        json += "\"ticket\":" + IntegerToString(OrderTicket()) + ",";
        json += "\"symbol\":" + BridgeJsonString(OrderSymbol()) + ",";
        json += "\"position_type\":" + BridgeJsonString(position_type) + ",";
        json += "\"lots\":" + DoubleToString(OrderLots(), 2) + ",";
        json += "\"open_price\":" + DoubleToString(OrderOpenPrice(), Digits) + ",";
        json += "\"open_time\":" + BridgeJsonDateTime(OrderOpenTime()) + ",";
        json += "\"magic_number\":" + IntegerToString(OrderMagicNumber()) + ",";
        json += "\"comment\":" + BridgeJsonString(OrderComment());
        json += "}";
    }

    json += "]";
    json += "}";

    return json;
}

bool BridgeWriteMarketSnapshot(const BridgeSettings &settings)
{
    RefreshRates();

    MqlRates rates[];
    ArrayResize(rates, settings.bars_to_export);

    ResetLastError();
    int copied = CopyRates(settings.target_symbol, settings.bars_timeframe, 0, settings.bars_to_export, rates);
    if(copied <= 0)
    {
        PrintFormat(
            "BridgeWriteMarketSnapshot: CopyRates failed symbol=%s timeframe=%d err=%d",
            settings.target_symbol,
            (int)settings.bars_timeframe,
            GetLastError()
        );
        return false;
    }

    string json = BridgeBuildMarketSnapshotJson(settings, rates, copied);
    return BridgeWriteTextFileAtomic(settings, BridgeMarketSnapshotPath(settings), json);
}

bool BridgeWriteRuntimeStatus(const BridgeSettings &settings, const string mode, const string detail)
{
    string json = BridgeBuildRuntimeStatusJson(settings, mode, detail);
    return BridgeWriteTextFileAtomic(settings, BridgeRuntimeStatusPath(settings), json);
}

bool BridgeWritePositionSnapshot(const BridgeSettings &settings)
{
    string json = BridgeBuildPositionSnapshotJson(settings);
    return BridgeWriteTextFileAtomic(settings, BridgePositionSnapshotPath(settings), json);
}

bool BridgeWriteAllSnapshots(const BridgeSettings &settings, const string mode, const string detail)
{
    bool market_ok = BridgeWriteMarketSnapshot(settings);
    bool status_ok = BridgeWriteRuntimeStatus(settings, mode, detail);
    bool position_ok = BridgeWritePositionSnapshot(settings);
    return market_ok && status_ok && position_ok;
}

#endif