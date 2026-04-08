// mt4/MQL4/Include/Bridge/BridgeUtils.mqh
#ifndef __BRIDGE_UTILS_MQH__
#define __BRIDGE_UTILS_MQH__

string BridgeJsonEscape(string value)
{
    StringReplace(value, "\\", "\\\\");
    StringReplace(value, "\"", "\\\"");
    StringReplace(value, "\r", "\\r");
    StringReplace(value, "\n", "\\n");
    StringReplace(value, "\t", "\\t");
    return value;
}

string BridgeJsonString(string value)
{
    return "\"" + BridgeJsonEscape(value) + "\"";
}

string BridgeJsonBool(bool value)
{
    return value ? "true" : "false";
}

string BridgeJsonInt(int value)
{
    return IntegerToString(value);
}

string BridgeJsonLong(long value)
{
    return IntegerToString((int)value);
}

string BridgeJsonDouble(double value, int digits)
{
    return DoubleToString(value, digits);
}

string BridgeJsonDateTime(datetime value)
{
    return BridgeJsonString(TimeToString(value, TIME_DATE | TIME_SECONDS));
}

string BridgeTimeframeToString(ENUM_TIMEFRAMES timeframe)
{
    switch (timeframe)
    {
        case PERIOD_M1: return "M1";
        case PERIOD_M5: return "M5";
        case PERIOD_M15: return "M15";
        case PERIOD_M30: return "M30";
        case PERIOD_H1: return "H1";
        case PERIOD_H4: return "H4";
        case PERIOD_D1: return "D1";
        case PERIOD_W1: return "W1";
        case PERIOD_MN1: return "MN1";
        default: return IntegerToString((int)timeframe);
    }
}

string BridgeBuildJsonBars(MqlRates &rates[], int copied, int price_digits)
{
    string json = "[";

    for (int i = 0; i < copied; i++)
    {
        if (i > 0)
        {
            json += ",";
        }

        json += "{";
        json += "\"time\":" + BridgeJsonDateTime(rates[i].time) + ",";
        json += "\"open\":" + BridgeJsonDouble(rates[i].open, price_digits) + ",";
        json += "\"high\":" + BridgeJsonDouble(rates[i].high, price_digits) + ",";
        json += "\"low\":" + BridgeJsonDouble(rates[i].low, price_digits) + ",";
        json += "\"close\":" + BridgeJsonDouble(rates[i].close, price_digits) + ",";
        json += "\"tick_volume\":" + IntegerToString((int)rates[i].tick_volume) + ",";
        json += "\"spread\":" + IntegerToString(rates[i].spread);
        json += "}";
    }

    json += "]";
    return json;
}

#endif