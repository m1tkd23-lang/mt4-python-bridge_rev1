// MQL4/Experts/BridgeWriterEA.mq4
#property strict

#include <Bridge/BridgeConfig.mqh>
#include <Bridge/BridgeFileIO.mqh>
#include <Bridge/BridgeSnapshotWriter.mqh>
#include <Bridge/BridgeCommandProcessor.mqh>

input string InpBridgeRoot = "mt4-python-bridge";
input ENUM_TIMEFRAMES InpBarsTimeframe = PERIOD_M1;
input int InpBarsToExport = 50;
input bool InpUseCommonFiles = false;
input bool InpWriteSnapshotOnInit = true;

// execution settings
input bool InpEnableCommandExecution = true;
input int InpRangeMagicNumber = 44001;
input int InpTrendMagicNumber = 44002;
input double InpFixedLot = 0.01;
input int InpSlippagePoints = 30;
input bool InpAllowBuy = true;
input bool InpAllowSell = true;

BridgeSettings g_settings;

int OnInit()
{
    g_settings.root_path = InpBridgeRoot;
    g_settings.use_common_files = InpUseCommonFiles;
    g_settings.bars_timeframe = InpBarsTimeframe;
    g_settings.bars_to_export = InpBarsToExport;
    g_settings.target_symbol = Symbol();
    g_settings.ea_name = "BridgeWriterEA";
    g_settings.ea_version = "0.4.0";

    g_settings.enable_command_execution = InpEnableCommandExecution;
    g_settings.range_magic_number = InpRangeMagicNumber;
    g_settings.trend_magic_number = InpTrendMagicNumber;
    g_settings.fixed_lot = InpFixedLot;
    g_settings.slippage_points = InpSlippagePoints;
    g_settings.allow_buy = InpAllowBuy;
    g_settings.allow_sell = InpAllowSell;

    if(!BridgeEnsureBaseLayout(g_settings))
    {
        Print("BridgeWriterEA: failed to ensure bridge directory layout.");
        BridgeWriteRuntimeStatus(g_settings, "init_failed", "directory layout error");
        return(INIT_FAILED);
    }

    if(InpWriteSnapshotOnInit)
    {
        if(!BridgeWriteAllSnapshots(g_settings, "normal", "initialized"))
        {
            Print("BridgeWriterEA: initial snapshot write failed.");
        }
    }

    Print("BridgeWriterEA: initialized successfully.");
    return(INIT_SUCCEEDED);
}

void OnTick()
{
    if(!BridgeWriteAllSnapshots(g_settings, "normal", "tick"))
    {
        Print("BridgeWriterEA: snapshot write failed on tick.");
    }

    if(g_settings.enable_command_execution)
    {
        BridgeProcessNextCommand(g_settings);
    }
}

void OnDeinit(const int reason)
{
    string detail = StringFormat("deinit_reason=%d", reason);
    BridgeWriteRuntimeStatus(g_settings, "stopped", detail);
}