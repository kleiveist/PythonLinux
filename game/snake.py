import curses
import random
import time

# Spielvariablen
FPS = 15
HEAD_CHAR    = 'O'
BODY_CHAR    = 'o'
FOOD_CHAR    = 'x'
POISON_CHAR  = 'x'
POISON_FLASH = 'X'
FLASH_MIN    = 1    # früheste Sekunde bis zum nächsten Flash
FLASH_MAX    = 3   # späteste Sekunde bis zum nächsten Flash
FLASH_DUR    = 0.4  # Dauer in Sekunden
INITIAL_LIVES  = 3      # Anzahl der Leben am Spielanfang

DIRS = {
    curses.KEY_UP:    (-1,  0),
    curses.KEY_DOWN:  ( 1,  0),
    curses.KEY_LEFT:  ( 0, -1),
    curses.KEY_RIGHT: ( 0,  1),
}

def get_count(score):
    return 2 + (score//2)*2

def place_items(exclude, max_y, max_x, n):
    items = []
    while len(items) < n:
        y = random.randint(1, max_y-2)
        x = random.randint(1, max_x-2)
        if (y, x) not in exclude and (y, x) not in items:
            items.append((y, x))
    return items

def play(stdscr):
    max_y, max_x = stdscr.getmaxyx()
    lives = INITIAL_LIVES
    score = 0

    def reset_snake():
        return [(max_y//2, max_x//2 + i) for i in range(2, -1, -1)]

    snake     = reset_snake()
    direction = DIRS[curses.KEY_RIGHT]

    # Initial spawn
    count     = get_count(score)
    food      = place_items(snake, max_y, max_x, count)
    poison    = place_items(snake + food, max_y, max_x, count)

    # Flash-Logik
    poison_flash     = False
    next_flash_start = time.time() + random.uniform(FLASH_MIN, FLASH_MAX)
    flash_end        = 0

    stdscr.nodelay(True)
    stdscr.clear()

    while True:
        t0 = time.time()
        # Input
        key = stdscr.getch()
        if key in DIRS:
            dy, dx = DIRS[key]
            if (dy,dx) != (-direction[0], -direction[1]):
                direction = (dy, dx)

        # Flash-Logik
        now = time.time()
        if not poison_flash and now >= next_flash_start:
            poison_flash = True
            flash_end    = now + FLASH_DUR
        if poison_flash and now >= flash_end:
            poison_flash     = False
            next_flash_start = now + random.uniform(FLASH_MIN, FLASH_MAX)

        # Bewegung
        head     = snake[0]
        new_head = (head[0] + direction[0], head[1] + direction[1])

        # Kollision?
        died = (
            new_head[0] in (0, max_y-1) or
            new_head[1] in (0, max_x-1) or
            new_head in snake or
            new_head in poison
        )
        if died:
            lives -= 1
            if lives <= 0:
                return score  # Ende, wenn keine Leben mehr
            # Leben verloren: kurz anzeigen und zurücksetzen
            stdscr.nodelay(False)
            stdscr.clear()
            msg = f' Leben verloren! Verbleibende Leben: {lives} '
            stdscr.addstr(max_y//2, (max_x-len(msg))//2, msg)
            stdscr.refresh()
            time.sleep(1.5)
            # Snake & Richtung zurücksetzen
            snake     = reset_snake()
            direction = DIRS[curses.KEY_RIGHT]
            stdscr.nodelay(True)
            continue

        snake.insert(0, new_head)

        # Futter essen
        if new_head in food:
            score += 1
            food.remove(new_head)
            if not food:
                count  = get_count(score)
                food   = place_items(snake, max_y, max_x, count)
                poison = place_items(snake + food, max_y, max_x, count)
                poison_flash     = False
                next_flash_start = time.time() + random.uniform(FLASH_MIN, FLASH_MAX)
        else:
            snake.pop()

        # Zeichnen
        stdscr.clear()
        stdscr.border()
        # Statuszeile Lives + Score
        status = f' Lives: {lives}   Score: {score} '
        stdscr.addstr(0, 2, status)
        # Futter
        for y,x in food:
            stdscr.addch(y, x, FOOD_CHAR)
        # Giftköder
        ch = POISON_FLASH if poison_flash else POISON_CHAR
        for y,x in poison:
            stdscr.addch(y, x, ch)
        # Schlange
        stdscr.addch(new_head[0], new_head[1], HEAD_CHAR)
        for y,x in snake[1:]:
            stdscr.addch(y, x, BODY_CHAR)

        stdscr.refresh()

        # Frame-Limit
        dt = time.time() - t0
        if dt < 1/FPS:
            time.sleep(1/FPS - dt)

def main(stdscr):
    curses.curs_set(0)
    while True:
        score = play(stdscr)
        # Game Over
        stdscr.nodelay(False)
        stdscr.clear()
        max_y, max_x = stdscr.getmaxyx()
        msg  = f' GAME OVER! Endstand: {score} '
        opts = '[n] Neues Spiel    [q] Beenden'
        stdscr.addstr(max_y//2    , (max_x - len(msg))//2, msg)
        stdscr.addstr(max_y//2 + 2, (max_x - len(opts))//2, opts)
        stdscr.refresh()
        # Auswahl
        while True:
            k = stdscr.getch()
            if k in (ord('n'), ord('N')):
                break
            if k in (ord('q'), ord('Q')):
                return

if __name__ == '__main__':
    curses.wrapper(main)