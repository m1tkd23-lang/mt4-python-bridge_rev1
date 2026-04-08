// MQL4/Include/Bridge/BridgeConfig.mqh
#ifndef __BRIDGE_CONFIG_MQH__
#define __BRIDGE_CONFIG_MQH__

struct BridgeSettings
{
    string root_path;
    bool use_common_files;
    ENUM_TIMEFRAMES bars_timeframe;
    int bars_to_export;
    string target_symbol;
    string ea_name;
    string ea_version;

    bool enable_command_execution;

    int range_magic_number;
    int trend_magic_number;

    double fixed_lot;
    int slippage_points;
    bool allow_buy;
    bool allow_sell;
};

int BridgeCommonFlag(const BridgeSettings &settings)
{
    return settings.use_common_files ? FILE_COMMON : 0;
}

int BridgeTextWriteFlags(const BridgeSettings &settings)
{
    int flags = FILE_WRITE | FILE_TXT | FILE_ANSI;
    if(settings.use_common_files)
    {
        flags |= FILE_COMMON;
    }
    return flags;
}

int BridgeTextReadFlags(const BridgeSettings &settings)
{
    int flags = FILE_READ | FILE_TXT | FILE_ANSI;
    if(settings.use_common_files)
    {
        flags |= FILE_COMMON;
    }
    return flags;
}

string BridgeRootPath(const BridgeSettings &settings)
{
    return settings.root_path;
}

string BridgeCommandQueuePath(const BridgeSettings &settings)
{
    return settings.root_path + "\\command_queue";
}

string BridgeResultQueuePath(const BridgeSettings &settings)
{
    return settings.root_path + "\\result_queue";
}

string BridgeStatePath(const BridgeSettings &settings)
{
    return settings.root_path + "\\state";
}

string BridgeLogsPath(const BridgeSettings &settings)
{
    return settings.root_path + "\\logs";
}

string BridgeMarketSnapshotPath(const BridgeSettings &settings)
{
    return settings.root_path + "\\market_snapshot.json";
}

string BridgeRuntimeStatusPath(const BridgeSettings &settings)
{
    return settings.root_path + "\\runtime_status.json";
}

string BridgePositionSnapshotPath(const BridgeSettings &settings)
{
    return settings.root_path + "\\position_snapshot.json";
}

bool BridgeIsManagedMagicNumber(const BridgeSettings &settings, const int magic_number)
{
    return (
        magic_number == settings.range_magic_number ||
        magic_number == settings.trend_magic_number
    );
}

int BridgeGetMagicNumberForLane(const BridgeSettings &settings, const string lane)
{
    if(lane == "range")
    {
        return settings.range_magic_number;
    }

    if(lane == "trend")
    {
        return settings.trend_magic_number;
    }

    return 0;
}

#endif