// Samp Language Compiler v0.2.0 - generated from example.smpl
forward Saitama(id);

new number = 10;

new Float:decimal = 10.0;

new pawn[64];

new id;

public OnGameModeInit()
{
    if (number > 7 || number == 7)
    {
        return false;
    }
    if (strcmp(pawn, "Hard", false) == 0)
    {
        SendClientMessage(id, 0x00ff00ff, "Why not use SAMP LANGUAGE?");
    }
    if (number > 10 || number == 10)
    {
        new str[32];
        SendClientMessage(id, 0xffffffff, str);
    }
}

public OnPlayerConnect(id)
{
    return true;
}

public Saitama(id)
{
    return true;
}
