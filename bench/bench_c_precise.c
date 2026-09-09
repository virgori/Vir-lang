#include <stdio.h>
#include <math.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>

static double elapsed_us(struct timespec t0, struct timespec t1) {
    return ((t1.tv_sec-t0.tv_sec)*1e9 + (t1.tv_nsec-t0.tv_nsec)) / 1000.0;
}

void bench_softmax() {
    int N = 100000;
    double *x = malloc(N*8);
    volatile double *out = malloc(N*8);
    for(int i=0;i<N;i++) x[i]=(double)i*0.001-50.0;
    struct timespec t0,t1;
    clock_gettime(CLOCK_MONOTONIC,&t0);
    for(int rep=0;rep<200;rep++) {
        double rm=x[0], se=1.0;
        for(int i=1;i<N;i++) {
            if(x[i]>rm) { se=se*exp(rm-x[i]); rm=x[i]; se+=1.0; }
            else { se+=exp(x[i]-rm); }
        }
        double inv=1.0/se;
        for(int i=0;i<N;i++) out[i]=exp(x[i]-rm)*inv;
    }
    clock_gettime(CLOCK_MONOTONIC,&t1);
    printf("Softmax(100K): %.3f us\n", elapsed_us(t0,t1)/200.0);
    free(x); free((void*)out);
}

void bench_welford() {
    int N = 1000000;
    double *x = malloc(N*8);
    for(int i=0;i<N;i++) x[i]=(double)i*0.001;
    struct timespec t0,t1;
    clock_gettime(CLOCK_MONOTONIC,&t0);
    volatile double var_val = 0;
    for(int rep=0;rep<100;rep++) {
        double mean=0, m2=0, comp=0;
        for(int i=0;i<N;i++) {
            double delta=x[i]-mean;
            mean+=delta/(i+1);
            double delta2=x[i]-mean;
            double term=delta*delta2;
            double y=term-comp;
            double s=m2+y;
            comp=(s-m2)-y;
            m2=s;
        }
        var_val=m2/(double)N;
    }
    clock_gettime(CLOCK_MONOTONIC,&t1);
    printf("Welford(1M): %.3f us\n", elapsed_us(t0,t1)/100.0);
    free(x);
}

void bench_fusion() {
    int N = 1000000;
    double *a=malloc(N*8), *b=malloc(N*8), *c=malloc(N*8);
    volatile double *out=malloc(N*8);
    for(int i=0;i<N;i++) { a[i]=i*0.001; b[i]=i*0.002; c[i]=i*0.003; }
    struct timespec t0,t1;
    clock_gettime(CLOCK_MONOTONIC,&t0);
    for(int rep=0;rep<200;rep++) {
        for(int i=0;i<N;i++) {
            double v = a[i]*b[i]+c[i];
            out[i] = v > 0.0 ? v : 0.0;
        }
    }
    clock_gettime(CLOCK_MONOTONIC,&t1);
    printf("EWFused(1M): %.3f us\n", elapsed_us(t0,t1)/200.0);

    clock_gettime(CLOCK_MONOTONIC,&t0);
    for(int rep=0;rep<200;rep++) {
        double *t1b=malloc(N*8), *t2b=malloc(N*8);
        for(int i=0;i<N;i++) t1b[i]=a[i]*b[i];
        for(int i=0;i<N;i++) t2b[i]=t1b[i]+c[i];
        for(int i=0;i<N;i++) out[i]=t2b[i]>0?t2b[i]:0;
        free(t1b); free(t2b);
    }
    clock_gettime(CLOCK_MONOTONIC,&t1);
    printf("EWUnfused(1M): %.3f us\n", elapsed_us(t0,t1)/200.0);
    free(a);free(b);free(c);free((void*)out);
}

void bench_dot() {
    int N = 10000000;
    double *a=malloc(N*8), *b=malloc(N*8);
    for(int i=0;i<N;i++) { a[i]=(double)i*1e-6; b[i]=(double)i*1e-6; }
    struct timespec t0,t1;
    clock_gettime(CLOCK_MONOTONIC,&t0);
    volatile double result=0;
    for(int rep=0;rep<50;rep++) {
        double s=0,comp=0;
        for(int i=0;i<N;i++) {
            double y=a[i]*b[i]-comp;
            double t=s+y;
            comp=(t-s)-y;
            s=t;
        }
        result=s;
    }
    clock_gettime(CLOCK_MONOTONIC,&t1);
    printf("KahanDot(10M): %.3f us\n", elapsed_us(t0,t1)/50.0);
    free(a);free(b);
}

int main() {
    bench_softmax();
    bench_welford();
    bench_fusion();
    bench_dot();
    return 0;
}
