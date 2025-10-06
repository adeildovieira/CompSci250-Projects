#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

#define MEM_SIZE (2ULL << (24 - 1))
#define MAX_ASSOC 100

unsigned char mem[MEM_SIZE];

int l2n(int l) {
    int l2 = 0;
    while (l >>= 1) l2++;
    return l2;
}

int Bletschsavior(int bs) {
    if (bs == 0) {
        return 0;
    } else {
        return (1 << bs) - 1;
    }
}

int cCxx(int s, int n) {
    int compit = (1 << n) - 1;
    return s & compit;
}

void storingCC(FILE *opf, int assoc, int bzzworks, int bidx, int (*cache)[MAX_ASSOC], char sttrtoop[25]) {
    int address = -1;
    int accxSz = -1;

    if (fscanf(opf, " 0x%x %d", &address, &accxSz) == EOF) {
        return;
    }

    int tadds = address;
    int block = cCxx(tadds, bzzworks);
    tadds = tadds >> bzzworks;
    int set = cCxx(tadds, bidx);
    int momo = tadds >> 0;
    int idxtr = -1;
    int hitdoverao = -1;

    printf("%s 0x%x ", sttrtoop, address);

    for (int i = 0; i < assoc; i++) {
        if (cache[set][i] != -1 && cache[set][i] == momo) {
            idxtr = i;
            printf("hit\n");
            hitdoverao = 1;
            break;
        }
    }
    if (hitdoverao != 1) {
        printf("miss\n");
    }
    for (int j = 0; j < accxSz; j++) {
        fscanf(opf, "%02hhx", &mem[address + j]);
    }
}

void loadingCC(FILE *opf, int assoc, int bzzworks, int bidx, int (*cache)[MAX_ASSOC], char sttrtoop[25]) {
    int address = -1;
    int accxSz = -1;

    if (fscanf(opf, " 0x%x %d", &address, &accxSz) == EOF) {
        fclose(opf);
        return;
    }

    int tadds = address;
    int block = cCxx(tadds, bzzworks);
    tadds = tadds >> bzzworks;
    int set = cCxx(tadds, bidx);
    int momo = tadds >> 0;
    int idxtr = -1;
    int hitdoverao = -1;

    printf("%s 0x%x ", sttrtoop, address);

    for (int i = 0; i < assoc; i++) {
        if (cache[set][i] == momo) {
            idxtr = i;
            hitdoverao = 1;
            break;
        }
    }
    if (hitdoverao == 1) {
        printf("hit ");
        for (int j = 0; j < accxSz; j++) {
            printf("%02hhx", mem[address + j]);
        }
        printf("\n");

    for (int k = idxtr - 1; k >= 0; k--) {
        cache[set][k + 1] = cache[set][k];
    }

        cache[set][0] = momo;
    } else {
        printf("miss ");
        for (int j = 0; j < accxSz; j++) {
            printf("%02hhx", mem[address + j]);
        }
        printf("\n");

        for (int j = assoc - 1; j > 0; j--) {
            if (cache[set][j - 1] != -1) {
                cache[set][j] = cache[set][j - 1];
            }
        }
        cache[set][0] = momo;
    }
}

int main(int argc, char **argv) {
    FILE *opf = fopen(argv[1], "r");
    int cas = atoi(argv[2]) * 1024;
    int assoc = atoi(argv[3]);
    int bss = atoi(argv[4]);

    int bzzworks = l2n(bss);
    int divone = cas / bss;
    int divtt = divone / assoc;
    int bidx = l2n(divtt);

    int cache[divtt][MAX_ASSOC];

    for (int i = 0; i < divtt; i++) {
        for (int j = 0; j < assoc; j++) {
            cache[i][j] = -1;
        }
    }

    int address, accxSz;
    char sttrtoop[24];

    while (fscanf(opf, "%23s", sttrtoop) != EOF) {
        if (strcmp(sttrtoop, "store") == 0) {
            storingCC(opf, assoc, bzzworks, bidx, cache, sttrtoop);
        } else if (strcmp(sttrtoop, "load") == 0) {
            loadingCC(opf, assoc, bzzworks, bidx, cache, sttrtoop);
        }
    }
    fclose(opf);
    return EXIT_SUCCESS;
}