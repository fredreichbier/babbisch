typedef struct {
    int a;
    char b;
    double c[];
} *Foobar;

typedef enum Yummy {
    A,
    B,
    THREE = 3,
    FOUR,
    DEADBEEF = 0xdeadbeef,
    NEXT
} Yummy;

int *testfunc(Foobar arg, ...);
