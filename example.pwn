// Samp Language Compiler
new Float:spawn_x = 1958.3;

new Float:spawn_y = 1343.1;

new Float:spawn_z = 15.3;

new starter_money = 5000;

public OnGameModeInit()
{
    SendClientMessageToAll(0xFFFFFFFF, "Roleplay Server is now ONLINE!");
    return true;
}

public OnGameModeExit()
{
    SendClientMessageToAll(0xFFFFFFFF, "Server is shutting down...");
    return true;
}

public OnPlayerConnect(id)
{
    SendClientMessage(id, 0x00FF00FF, "Welcome to RP Server!");
    SendClientMessage(id, 0xFFFFFFFF, "Use /help to see available commands");
    GivePlayerMoney(id, starter_money);
    return true;
}

public OnPlayerDisconnect(id, reason)
{
    SendClientMessageToAll(0xFFFFFFFF, "A player has left the server.");
    return true;
}

public OnPlayerSpawn(id)
{
    SetPlayerPos(id, spawn_x, spawn_y, spawn_z);
    SetPlayerHealth(id, 100.0);
    SetPlayerArmour(id, 0.0);
    return true;
}

CMD:help(id, params[])
{
    SendClientMessage(id, 0xFFFFFFFF, "===== HELP MENU =====");
    SendClientMessage(id, 0x00FF00FF, "/me [action] - roleplay action");
    SendClientMessage(id, 0x00FF00FF, "/do [desc] - describe situation");
    SendClientMessage(id, 0x00FF00FF, "/givecash [id] [amount]");
    return true;
}

CMD:me(id, params[])
{
    if (strcmp(params, "") == 0)
    {
        SendClientMessage(id, 0xFF0000FF, "Usage: /me [action]");
        return false;
    }
    SendClientMessageToAll(0xFFFF00FF, "* Player performs: {params}");
    return true;
}

CMD:do(id, params[])
{
    if (strcmp(params, "") == 0)
    {
        SendClientMessage(id, 0xFF0000FF, "Usage: /do [description]");
        return false;
    }
    SendClientMessageToAll(0xFFAA00FF, "* {params}");
    return true;
}

CMD:givecash(id, params[])
{
    new target;
    new amount;
    if (sscanf(params, "ii", target, amount) > 0)
    {
        SendClientMessage(id, 0xFF0000FF, "Usage: /givecash [id] [amount]");
        return false;
    }
    if (amount < 1)
    {
        SendClientMessage(id, 0xFF0000FF, "Invalid amount");
        return false;
    }
    GivePlayerMoney(id, (amount * (0 - 1)));
    GivePlayerMoney(target, amount);
    SendClientMessage(id, 0x00FF00FF, "You gave money successfully");
    SendClientMessage(target, 0x00FF00FF, "You received money from a player");
    return true;
}
