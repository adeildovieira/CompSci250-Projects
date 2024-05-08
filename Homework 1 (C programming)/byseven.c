#include "stdio.h"
#include "stdlib.h"


int main(int argc, char* argv[]){
    // int contador = 0;
    // int numerostestes = 1;
    // int inputcomando = argc;

    int numeros = atoi(argv[1]);

    for (int i = 1; numeros > 0; i++) {
        if (i%7 == 0) {
            printf("%d\n", i);
            numeros--;
        }
    }

    // while (contador <= inputcomando+1) {
    //     if (numerostestes%7 == 0) {
    //         printf("%d\n", numerostestes);
    //         contador++;
    //     } numerostestes++;
    // }

//     for (int argc; i < argc.size; i++) {
//         if (i%7 == 0) {
//             return int;
//             printf(%d; /n);
//         }
//     }
// }

return EXIT_SUCCESS;
}

// input: N;
// processes: [i] from 0 to N of %7 numbers int;
// returns: these i numbers each in a line then I should use /n.