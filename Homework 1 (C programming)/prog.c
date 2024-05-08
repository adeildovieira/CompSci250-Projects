#include "stdio.h"
#include "stdlib.h"
int m_w = 123;    /* must not be zero */
int m_z = 234;    /* must not be zero */
inline int get_random(){
	m_z = 36969 * (m_z & 65535) + (m_z >> 16);
	m_w = 18000 * (m_w & 65535) + (m_w >> 16);
	return (m_z << 16) + m_w;  /* 32-bit result */
}
int main(int argc, char ** argv){
	int runs = 1;
	int s = 512;
	int * a =(int*)malloc(s*s*sizeof(int));
	int * b =(int*)malloc(s*s*sizeof(int));
	int * c =(int*)malloc(s*s*sizeof(int));
	int i, j;
	for(i=0; i<s; i++){
		for(j=0; j<s; j++){
			a[i+s*j]=get_random();
			b[i+s*j]=get_random();
		}
	}
	long tmp;
	int n;
	for(n=0;n<runs;n++){
		tmp=0;
		for(i=0;i<s;i++){
			for(j=0;j<s;j++){
				tmp=0;
				int k;
				for(k=0;k<s;k++){
					tmp+=a[i+s*k]*b[k+s*j];
				}
				c[i+s*j]=tmp;
			}
		}
	}
	i = ((unsigned)get_random())%s;
	j = ((unsigned)get_random())%s;
	printf("C[%d][%d]=%d\n",i,j,c[i+s*j]);
}
