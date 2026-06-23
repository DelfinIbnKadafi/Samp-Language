# Samp-Language

A specialized programming language designed for SA-MP

Example :
```smpl
PlayerJoin(id)
    if id bigger 7
        return true
    else
        return false
    return true
```

# Why is better?

In this language, you doesn't need any complicated symbol,
just use English language.

Seems like python but different.

1. Operator symbols

```
 == : is
 != : not
 >  : bigger
 <  : smaller
 && : and
 || : or
```

a. If block

Example :
```smpl
if pawn is "Hard"
    Send(id, 00ff00ff, "Why not use SAMP LANGUAGE?")

if number bigger 10 or number is 10
    Send(id, ffffffff, "Number is {number}")
```

2. Variable

Use **let** for declaration.

Example :

```smpl
let int_var : integer
let str_var : string
let float_var : float
let bool_var : bool
```

How to use?

You can use this symbol for change variable value

Example :
```smpl
let isnotpawn : bool

main()
    isnotpawn = true
```

Or you want to reduce value?
Just use negative symbol

Example :
```smpl
let isnumber : integer = 11

main()
    isnumber = number - 10

// and now, isnumber = 1
```

For another guide, read GUIDE.md

# Installation

Clone this repository or Download latest release

```Bash
git clone https://github.com/DelfinIbnKadafi/Samp-Language.git
```

Open compiler folder
```
cd Samp-Language
```

compile your smpl file
```
python compiler/smplc.py fil_name.smpl
```

# License

Apatche 2.0
