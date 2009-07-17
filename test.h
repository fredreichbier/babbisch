typedef struct _Foobar {
    int a;
    char b;
    double c[];
    struct _Foobar *foobar;
} Foobar;

enum Yummy {
    A,
    B,
    THREE = 3,
    FOUR,
    DEADBEEF = 0xdeadbeef,
    NEXT
};

int testfunc(struct Foobar arg, ...);
