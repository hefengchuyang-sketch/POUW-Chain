#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>

#define SBOX_SIZE 256

static inline int parity8(uint8_t v) {
    int p = 0;
    while (v) {
        p ^= (v & 1);
        v >>= 1;
    }
    return p;
}

static PyObject *max_walsh_spectrum(PyObject *self, PyObject *args) {
    PyObject *sbox_obj = NULL;
    PyObject *seq = NULL;
    uint8_t sbox[SBOX_SIZE];
    int max_vals[SBOX_SIZE] = {0};

    (void)self;

    if (!PyArg_ParseTuple(args, "O", &sbox_obj)) {
        return NULL;
    }

    seq = PySequence_Fast(sbox_obj, "sbox must be a sequence");
    if (seq == NULL) {
        return NULL;
    }

    if (PySequence_Fast_GET_SIZE(seq) != SBOX_SIZE) {
        Py_DECREF(seq);
        PyErr_SetString(PyExc_ValueError, "sbox length must be 256");
        return NULL;
    }

    for (int i = 0; i < SBOX_SIZE; i++) {
        PyObject *item = PySequence_Fast_GET_ITEM(seq, i);
        long v = PyLong_AsLong(item);
        if (PyErr_Occurred()) {
            Py_DECREF(seq);
            return NULL;
        }
        if (v < 0 || v > 255) {
            Py_DECREF(seq);
            PyErr_SetString(PyExc_ValueError, "sbox values must be in [0, 255]");
            return NULL;
        }
        sbox[i] = (uint8_t)v;
    }

    max_vals[0] = 0;

    for (int b = 1; b < SBOX_SIZE; b++) {
        int f[SBOX_SIZE];

        for (int x = 0; x < SBOX_SIZE; x++) {
            int exponent = parity8((uint8_t)(b & sbox[x]));
            f[x] = exponent == 0 ? 1 : -1;
        }

        for (int h = 1; h < SBOX_SIZE; h <<= 1) {
            for (int i = 0; i < SBOX_SIZE; i += (h << 1)) {
                for (int j = i; j < i + h; j++) {
                    int u = f[j];
                    int v = f[j + h];
                    f[j] = u + v;
                    f[j + h] = u - v;
                }
            }
        }

        int max_abs = 0;
        for (int a = 1; a < SBOX_SIZE; a++) {
            int val = f[a] < 0 ? -f[a] : f[a];
            if (val > max_abs) {
                max_abs = val;
            }
        }
        max_vals[b] = max_abs;
    }

    Py_DECREF(seq);

    PyObject *out = PyList_New(SBOX_SIZE);
    if (out == NULL) {
        return NULL;
    }

    for (int i = 0; i < SBOX_SIZE; i++) {
        PyObject *v = PyLong_FromLong(max_vals[i]);
        if (v == NULL) {
            Py_DECREF(out);
            return NULL;
        }
        PyList_SET_ITEM(out, i, v);
    }

    return out;
}

static PyMethodDef methods[] = {
    {"max_walsh_spectrum", max_walsh_spectrum, METH_VARARGS,
     "Compute max Walsh-Hadamard absolute spectrum for each component."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    "_sbox_accel",
    "Optional C accelerator for S-Box scoring hot path.",
    -1,
    methods,
};

PyMODINIT_FUNC PyInit__sbox_accel(void) {
    return PyModule_Create(&module);
}
