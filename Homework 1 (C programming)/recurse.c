#include "stdio.h"
#include "stdlib.h"

int recursion(int N) { // NOT using pointer here anymore.
    
    if (N <= 0) {
        return 2;
    }
    return 3 * (N-1) + recursion(N - 1) + 1;
}

// int recursion(int* N) {
//     int i = *N;
    
//     if (i <= 0) {
//         return 0;
//     }
//     return 3*(i-1) + recursion(N - 1) + 1;
// }

int main(int argc, char* argv[]) {

    int a = atoi(argv[1]);
    int rec = recursion(a);
    printf("%d", rec);
    return EXIT_SUCCESS;

// int main() {
//     int a = i;
//     printf("%d", a);
//     return EXIT_SUCCESS;
// }

}