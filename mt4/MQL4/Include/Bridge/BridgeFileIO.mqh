// MQL4/Include/Bridge/BridgeFileIO.mqh
#ifndef __BRIDGE_FILE_IO_MQH__
#define __BRIDGE_FILE_IO_MQH__

#include <Bridge/BridgeConfig.mqh>

bool BridgeEnsureDirectory(const string path, const bool use_common_files)
{
    int common_flag = use_common_files ? FILE_COMMON : 0;

    ResetLastError();
    bool created = FolderCreate(path, common_flag);
    int err = GetLastError();

    if(created)
    {
        return true;
    }

    if(err == 0)
    {
        return true;
    }

    PrintFormat("BridgeEnsureDirectory: path=%s err=%d", path, err);
    return false;
}

bool BridgeEnsureBaseLayout(const BridgeSettings &settings)
{
    bool ok = true;
    ok = BridgeEnsureDirectory(BridgeRootPath(settings), settings.use_common_files) && ok;
    ok = BridgeEnsureDirectory(BridgeCommandQueuePath(settings), settings.use_common_files) && ok;
    ok = BridgeEnsureDirectory(BridgeResultQueuePath(settings), settings.use_common_files) && ok;
    ok = BridgeEnsureDirectory(BridgeStatePath(settings), settings.use_common_files) && ok;
    ok = BridgeEnsureDirectory(BridgeLogsPath(settings), settings.use_common_files) && ok;
    return ok;
}

bool BridgeWriteTextFileAtomic(const BridgeSettings &settings, const string relative_path, const string content)
{
    string temp_path = relative_path + ".tmp";
    int write_flags = BridgeTextWriteFlags(settings);

    ResetLastError();
    int handle = FileOpen(temp_path, write_flags);
    if(handle == INVALID_HANDLE)
    {
        PrintFormat("BridgeWriteTextFileAtomic: FileOpen failed path=%s err=%d", temp_path, GetLastError());
        return false;
    }

    FileWriteString(handle, content, StringLen(content));
    FileFlush(handle);
    FileClose(handle);

    int common_flag = BridgeCommonFlag(settings);

    ResetLastError();
    FileDelete(relative_path, common_flag);

    ResetLastError();
    bool moved = FileMove(temp_path, common_flag, relative_path, common_flag);
    if(!moved)
    {
        PrintFormat("BridgeWriteTextFileAtomic: FileMove failed src=%s dst=%s err=%d", temp_path, relative_path, GetLastError());
        return false;
    }

    return true;
}

bool BridgeReadTextFile(const BridgeSettings &settings, const string relative_path, string &content)
{
    content = "";

    int read_flags = BridgeTextReadFlags(settings);

    ResetLastError();
    int handle = FileOpen(relative_path, read_flags);
    if(handle == INVALID_HANDLE)
    {
        PrintFormat("BridgeReadTextFile: FileOpen failed path=%s err=%d", relative_path, GetLastError());
        return false;
    }

    while(!FileIsEnding(handle))
    {
        content += FileReadString(handle);
    }

    FileClose(handle);
    return true;
}

bool BridgeDeleteFile(const BridgeSettings &settings, const string relative_path)
{
    int common_flag = BridgeCommonFlag(settings);

    ResetLastError();
    bool deleted = FileDelete(relative_path, common_flag);
    int err = GetLastError();

    if(deleted)
    {
        return true;
    }

    if(err == 0)
    {
        return true;
    }

    PrintFormat("BridgeDeleteFile: FileDelete failed path=%s err=%d", relative_path, err);
    return false;
}

#endif