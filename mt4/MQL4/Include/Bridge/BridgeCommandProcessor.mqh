// MQL4/Include/Bridge/BridgeCommandProcessor.mqh
#ifndef __BRIDGE_COMMAND_PROCESSOR_MQH__
#define __BRIDGE_COMMAND_PROCESSOR_MQH__

#include <Bridge/BridgeConfig.mqh>
#include <Bridge/BridgeFileIO.mqh>
#include <Bridge/BridgeUtils.mqh>

string BridgeJsonGetString(const string json, const string key)
{
    string token = "\"" + key + "\"";
    int key_pos = StringFind(json, token);
    if(key_pos < 0)
    {
        return "";
    }

    int colon_pos = StringFind(json, ":", key_pos);
    if(colon_pos < 0)
    {
        return "";
    }

    int len = StringLen(json);
    int i = colon_pos + 1;

    while(i < len)
    {
        int ch = StringGetChar(json, i);
        if(ch != 32 && ch != 9 && ch != 10 && ch != 13)
        {
            break;
        }
        i++;
    }

    if(i >= len)
    {
        return "";
    }

    if(StringGetChar(json, i) == 34)
    {
        i++;
        int start = i;

        while(i < len)
        {
            int ch2 = StringGetChar(json, i);
            if(ch2 == 34)
            {
                return StringSubstr(json, start, i - start);
            }
            i++;
        }
        return "";
    }

    int start_num = i;
    while(i < len)
    {
        int ch3 = StringGetChar(json, i);
        bool is_number_char =
            (ch3 >= 48 && ch3 <= 57) ||
            ch3 == 45 ||
            ch3 == 46 ||
            ch3 == 43 ||
            ch3 == 101 ||
            ch3 == 69;
        if(!is_number_char)
        {
            break;
        }
        i++;
    }

    return StringSubstr(json, start_num, i - start_num);
}

int BridgeJsonGetInt(const string json, const string key)
{
    string value = BridgeJsonGetString(json, key);
    if(value == "")
    {
        return -1;
    }
    return StrToInteger(value);
}

double BridgeJsonGetDouble(const string json, const string key)
{
    string value = BridgeJsonGetString(json, key);
    if(value == "")
    {
        return 0.0;
    }
    return StrToDouble(value);
}

string BridgeJsonGetMetaString(const string json, const string key)
{
    string meta_token = "\"meta\"";
    int meta_pos = StringFind(json, meta_token);
    if(meta_pos < 0)
    {
        return "";
    }

    int object_start = StringFind(json, "{", meta_pos);
    if(object_start < 0)
    {
        return "";
    }

    int len = StringLen(json);
    int depth = 0;
    int object_end = -1;

    for(int i = object_start; i < len; i++)
    {
        int ch = StringGetChar(json, i);
        if(ch == 123) // {
        {
            depth++;
        }
        else if(ch == 125) // }
        {
            depth--;
            if(depth == 0)
            {
                object_end = i;
                break;
            }
        }
    }

    if(object_end < 0)
    {
        return "";
    }

    string meta_json = StringSubstr(json, object_start, object_end - object_start + 1);
    return BridgeJsonGetString(meta_json, key);
}

int BridgeCountOpenPositionsByMagic(const BridgeSettings &settings, const int magic_number)
{
    int count = 0;

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

        if(OrderMagicNumber() != magic_number)
        {
            continue;
        }

        int type = OrderType();
        if(type == OP_BUY || type == OP_SELL)
        {
            count++;
        }
    }

    return count;
}

int BridgeCountOpenPositionsForLane(const BridgeSettings &settings, const string lane)
{
    int magic_number = BridgeGetMagicNumberForLane(settings, lane);
    if(magic_number == 0)
    {
        return 0;
    }

    return BridgeCountOpenPositionsByMagic(settings, magic_number);
}

string BridgeBuildResultJson(
    const string command_id,
    const string status,
    const string action,
    const int ticket,
    const int error_code,
    const string message
)
{
    string json = "{";
    json += "\"schema_version\":\"1.0\",";
    json += "\"command_id\":" + BridgeJsonString(command_id) + ",";
    json += "\"processed_at\":" + BridgeJsonDateTime(TimeCurrent()) + ",";
    json += "\"status\":" + BridgeJsonString(status) + ",";
    json += "\"action\":" + BridgeJsonString(action) + ",";
    json += "\"ticket\":" + IntegerToString(ticket) + ",";
    json += "\"error_code\":" + IntegerToString(error_code) + ",";
    json += "\"message\":" + BridgeJsonString(message);
    json += "}";

    return json;
}

bool BridgeWriteResult(
    const BridgeSettings &settings,
    const string command_id,
    const string status,
    const string action,
    const int ticket,
    const int error_code,
    const string message
)
{
    string result_filename = BridgeResultQueuePath(settings) + "\\result_" + command_id + ".json";
    string result_json = BridgeBuildResultJson(
        command_id,
        status,
        action,
        ticket,
        error_code,
        message
    );

    return BridgeWriteTextFileAtomic(settings, result_filename, result_json);
}

bool BridgeFindNextCommandFile(const BridgeSettings &settings, string &filename)
{
    filename = "";

    string mask = BridgeCommandQueuePath(settings) + "\\*.json";
    long handle = FileFindFirst(mask, filename, BridgeCommonFlag(settings));
    if(handle == INVALID_HANDLE)
    {
        return false;
    }

    FileFindClose(handle);
    return filename != "";
}

int BridgeExecuteMarketOrder(
    const BridgeSettings &settings,
    const string action,
    const string command_id,
    const string lane,
    const double sl,
    const double tp
)
{
    RefreshRates();

    int magic_number = BridgeGetMagicNumberForLane(settings, lane);
    if(magic_number == 0)
    {
        return -1;
    }

    double lot = settings.fixed_lot;
    int slippage = settings.slippage_points;
    string comment = "lane:" + lane + "|cmd:" + StringSubstr(command_id, 0, 24);

    if(action == "BUY")
    {
        return OrderSend(
            settings.target_symbol,
            OP_BUY,
            lot,
            Ask,
            slippage,
            sl,
            tp,
            comment,
            magic_number,
            0,
            clrBlue
        );
    }

    if(action == "SELL")
    {
        return OrderSend(
            settings.target_symbol,
            OP_SELL,
            lot,
            Bid,
            slippage,
            sl,
            tp,
            comment,
            magic_number,
            0,
            clrRed
        );
    }

    return -1;
}

bool BridgeExecuteCloseByTicket(const BridgeSettings &settings, const int ticket)
{
    if(ticket <= 0)
    {
        return false;
    }

    if(!OrderSelect(ticket, SELECT_BY_TICKET))
    {
        return false;
    }

    if(OrderSymbol() != settings.target_symbol)
    {
        return false;
    }

    if(!BridgeIsManagedMagicNumber(settings, OrderMagicNumber()))
    {
        return false;
    }

    RefreshRates();

    int type = OrderType();
    double lots = OrderLots();

    if(type == OP_BUY)
    {
        return OrderClose(ticket, lots, Bid, settings.slippage_points, clrYellow);
    }

    if(type == OP_SELL)
    {
        return OrderClose(ticket, lots, Ask, settings.slippage_points, clrYellow);
    }

    return false;
}

void BridgeProcessNextCommand(const BridgeSettings &settings)
{
    string filename = "";
    if(!BridgeFindNextCommandFile(settings, filename))
    {
        return;
    }

    string relative_path = BridgeCommandQueuePath(settings) + "\\" + filename;
    string raw_json = "";

    if(!BridgeReadTextFile(settings, relative_path, raw_json))
    {
        return;
    }

    string command_id = BridgeJsonGetString(raw_json, "command_id");
    string action = BridgeJsonGetString(raw_json, "action");
    string symbol = BridgeJsonGetString(raw_json, "symbol");
    string entry_lane = BridgeJsonGetMetaString(raw_json, "entry_lane");
    int ticket = BridgeJsonGetInt(raw_json, "ticket");
    double sl = BridgeJsonGetDouble(raw_json, "sl");
    double tp = BridgeJsonGetDouble(raw_json, "tp");

    if(command_id == "")
    {
        command_id = "unknown";
    }

    if(symbol != settings.target_symbol)
    {
        BridgeWriteResult(settings, command_id, "rejected", action, -1, 0, "symbol mismatch");
        BridgeDeleteFile(settings, relative_path);
        return;
    }

    if(action != "BUY" && action != "SELL" && action != "CLOSE")
    {
        BridgeWriteResult(settings, command_id, "rejected", action, -1, 0, "unsupported action");
        BridgeDeleteFile(settings, relative_path);
        return;
    }

    if(action == "BUY" && !settings.allow_buy)
    {
        BridgeWriteResult(settings, command_id, "rejected", action, -1, 0, "buy disabled");
        BridgeDeleteFile(settings, relative_path);
        return;
    }

    if(action == "SELL" && !settings.allow_sell)
    {
        BridgeWriteResult(settings, command_id, "rejected", action, -1, 0, "sell disabled");
        BridgeDeleteFile(settings, relative_path);
        return;
    }

    if(!IsTradeAllowed())
    {
        BridgeWriteResult(settings, command_id, "rejected", action, -1, 0, "trade not allowed");
        BridgeDeleteFile(settings, relative_path);
        return;
    }

    if(action == "CLOSE")
    {
        bool closed = BridgeExecuteCloseByTicket(settings, ticket);
        if(!closed)
        {
            int close_err = GetLastError();
            BridgeWriteResult(settings, command_id, "rejected", action, ticket, close_err, "close failed");
            BridgeDeleteFile(settings, relative_path);
            return;
        }

        BridgeWriteResult(settings, command_id, "closed", action, ticket, 0, "position closed");
        BridgeDeleteFile(settings, relative_path);
        return;
    }

    if(entry_lane != "range" && entry_lane != "trend")
    {
        BridgeWriteResult(settings, command_id, "rejected", action, -1, 0, "invalid entry lane");
        BridgeDeleteFile(settings, relative_path);
        return;
    }

    if(BridgeCountOpenPositionsForLane(settings, entry_lane) > 0)
    {
        BridgeWriteResult(settings, command_id, "rejected", action, -1, 0, "position already exists in lane");
        BridgeDeleteFile(settings, relative_path);
        return;
    }

    int new_ticket = BridgeExecuteMarketOrder(settings, action, command_id, entry_lane, sl, tp);
    if(new_ticket < 0)
    {
        int err = GetLastError();
        BridgeWriteResult(settings, command_id, "rejected", action, -1, err, "order send failed");
        BridgeDeleteFile(settings, relative_path);
        return;
    }

    BridgeWriteResult(settings, command_id, "filled", action, new_ticket, 0, "order filled");
    BridgeDeleteFile(settings, relative_path);
}

#endif