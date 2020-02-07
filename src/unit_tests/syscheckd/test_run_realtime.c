/*
 * Copyright (C) 2015-2019, Wazuh Inc.
 *
 * This program is free software; you can redistribute it
 * and/or modify it under the terms of the GNU General Public
 * License (version 2) as published by the FSF - Free Software
 * Foundation.
 */

#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>
#include <stdio.h>
#include <string.h>

#include "../syscheckd/syscheck.h"
#include "../config/syscheck-config.h"

/* redefinitons/wrapping */

int __wrap_inotify_init() {
    return mock();
}

int __wrap_inotify_add_watch() {
    return mock();
}

int __wrap_OSHash_Get_ex() {
    return mock();
}

char *__wrap_OSHash_Get() {
    static char * file = "test";
    return file;
}

int __wrap_OSHash_Add_ex() {
    return mock();
}

int __wrap_OSHash_Update_ex(OSHash *self, const char *key, void *data) {
    int retval = mock();

    if(retval != 0)
        free(data); //  This won't be used, free it

    return retval;
}

void * __wrap_rbtree_insert() {
    return NULL;
}

OSHash * __wrap_OSHash_Create() {
    return mock_type(OSHash*);
}

void __wrap__merror(const char * file, int line, const char * func, const char *msg, ...)
{
    char formatted_msg[OS_MAXSTR];
    va_list args;

    va_start(args, msg);
    vsnprintf(formatted_msg, OS_MAXSTR, msg, args);
    va_end(args);

    check_expected(formatted_msg);
}

ssize_t __real_read(int fildes, void *buf, size_t nbyte);
ssize_t __wrap_read(int fildes, void *buf, size_t nbyte) {
    static char event[] = {1, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 't', 'e', 's', 't', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
    switch(mock_type(int)){
        case 0:
        return __real_read(fildes, buf, nbyte);

        case 1:
        return mock_type(ssize_t);

        case 2:
        memcpy(buf, event, 32);
        return mock_type(ssize_t);
    }
    // We should never reach this point
    return __real_read(fildes, buf, nbyte);
}

int __wrap_os_random(void) {
    return mock();
}

int __wrap_W_Vector_insert_unique(W_Vector *v, const char *element) {
    check_expected_ptr(v);
    check_expected(element);

    return mock();
}

/* setup/teardown */
static int setup_group(void **state) {
    Read_Syscheck_Config("test_syscheck.conf");

    syscheck.realtime = (rtfim *) calloc(1, sizeof(rtfim));

    if(syscheck.realtime == NULL)
        return -1;

    return 0;
}

static int teardown_group(void **state) {
    free(syscheck.realtime);

    return 0;
}

#if defined(TEST_SERVER) || defined(TEST_AGENT)
    static int setup_w_vector(void **state)
    {
        audit_added_dirs = W_Vector_init(2);
        if(!audit_added_dirs)
            return -1;

        return 0;
    }

    static int teardown_w_vector(void **state)
    {
        W_Vector_free(audit_added_dirs);

        return 0;
    }
#endif

static int setup_realtime_start(void **state) {
    OSHash *hash = calloc(1, sizeof(OSHash));

    if(hash == NULL)
        return -1;

    *state = hash;

    // free the global syscheck.realtime before running syscheck_start
    free(syscheck.realtime);

    return 0;
}

static int teardown_realtime_start(void **state) {
    OSHash *hash = *state;

    free(hash);

    return 0;
}

/* tests */

void test_realtime_start_success(void **state) {
    OSHash *hash = *state;
    int ret;

    will_return(__wrap_OSHash_Create, hash);
    will_return(__wrap_inotify_init, 0);

    ret = realtime_start();

    assert_int_equal(ret, 0);
}


void test_realtime_start_failure_hash(void **state) {
    int ret;

    will_return(__wrap_OSHash_Create, NULL);

    errno = ENOMEM;
    expect_string(__wrap__merror, formatted_msg,
        "(1102): Could not acquire memory due to [(12)-(Cannot allocate memory)].");

    ret = realtime_start();

    errno = 0;
    assert_int_equal(ret, -1);
}


void test_realtime_start_failure_inotify(void **state) {
    OSHash *hash = *state;
    int ret;

    will_return(__wrap_OSHash_Create, hash);
    will_return(__wrap_inotify_init, -1);

    expect_string(__wrap__merror, formatted_msg, FIM_ERROR_INOTIFY_INITIALIZE);

    ret = realtime_start();

    assert_int_equal(ret, -1);
}

#if defined(TEST_SERVER) || defined(TEST_AGENT)

    void test_realtime_adddir_whodata(void **state) {
        int ret;

        const char * path = "/etc/folder";

        audit_thread_active = 1;

        expect_value(__wrap_W_Vector_insert_unique, v, audit_added_dirs);
        expect_string(__wrap_W_Vector_insert_unique, element, "/etc/folder");
        will_return(__wrap_W_Vector_insert_unique, 1);

        ret = realtime_adddir(path, 1);

        assert_int_equal(ret, 1);
    }

#endif


void test_realtime_adddir_realtime_failure(void **state)
{
    (void) state;
    int ret;

    const char * path = "/etc/folder";

    syscheck.realtime->fd = -1;

    ret = realtime_adddir(path, 0);

    assert_int_equal(ret, -1);
}


void test_realtime_adddir_realtime_add(void **state)
{
    (void) state;
    int ret;

    const char * path = "/etc/folder";

    syscheck.realtime->fd = 1;
    will_return(__wrap_inotify_add_watch, 1);
    will_return(__wrap_OSHash_Get_ex, 0);
    will_return(__wrap_OSHash_Add_ex, 1);

    ret = realtime_adddir(path, 0);

    assert_int_equal(ret, 1);
}


void test_realtime_adddir_realtime_update(void **state)
{
    (void) state;
    int ret;

    const char * path = "/etc/folder";

    syscheck.realtime->fd = 1;
    will_return(__wrap_inotify_add_watch, 1);
    will_return(__wrap_OSHash_Get_ex, 1);
    will_return(__wrap_OSHash_Update_ex, 1);

    ret = realtime_adddir(path, 0);

    assert_int_equal(ret, 1);
}


void test_realtime_adddir_realtime_update_failure(void **state)
{
    (void) state;
    int ret;

    const char * path = "/etc/folder";

    syscheck.realtime->fd = 1;
    will_return(__wrap_inotify_add_watch, 1);
    will_return(__wrap_OSHash_Get_ex, 1);
    will_return(__wrap_OSHash_Update_ex, 0);

    expect_string(__wrap__merror, formatted_msg, "Unable to update 'dirtb'. Directory not found: '/etc/folder'");

    ret = realtime_adddir(path, 0);

    assert_int_equal(ret, -1);
}

#if defined(TEST_SERVER) || defined(TEST_AGENT)
    void test_free_syscheck_dirtb_data(void **state)
    {
        (void) state;
        char *data = strdup("test");

        free_syscheck_dirtb_data(data);

        assert_non_null(data);
    }


    void test_free_syscheck_dirtb_data_null(void **state)
    {
        (void) state;
        char *data = NULL;

        free_syscheck_dirtb_data(data);

        assert_null(data);
    }


    void test_realtime_process(void **state)
    {
        (void) state;

        syscheck.realtime->fd = 1;

        will_return(__wrap_read, 1); // Use wrap
        will_return(__wrap_read, 0);

        realtime_process();
    }

    void test_realtime_process_len(void **state)
    {
        (void) state;

        syscheck.realtime->fd = 1;

        will_return(__wrap_read, 2); // Use wrap
        will_return(__wrap_read, 16);

        realtime_process();
    }

    void test_realtime_process_failure(void **state)
    {
        (void) state;

        syscheck.realtime->fd = 1;

        will_return(__wrap_read, 1); // Use wrap
        will_return(__wrap_read, -1);

        expect_string(__wrap__merror, formatted_msg, FIM_ERROR_REALTIME_READ_BUFFER);

        realtime_process();
    }
#endif

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test_setup_teardown(test_realtime_start_success, setup_realtime_start, teardown_realtime_start),
        cmocka_unit_test_setup_teardown(test_realtime_start_failure_hash, setup_realtime_start, teardown_realtime_start),
        cmocka_unit_test_setup_teardown(test_realtime_start_failure_inotify, setup_realtime_start, teardown_realtime_start),
        #if defined(TEST_SERVER) || defined(TEST_AGENT)
            cmocka_unit_test_setup_teardown(test_realtime_adddir_whodata, setup_w_vector, teardown_w_vector),
        #endif
        cmocka_unit_test(test_realtime_adddir_realtime_failure),
        cmocka_unit_test(test_realtime_adddir_realtime_add),
        cmocka_unit_test(test_realtime_adddir_realtime_update),
        cmocka_unit_test(test_realtime_adddir_realtime_update_failure),
        #if defined(TEST_SERVER) || defined(TEST_AGENT)
            cmocka_unit_test(test_free_syscheck_dirtb_data),
            cmocka_unit_test(test_free_syscheck_dirtb_data_null),
            cmocka_unit_test(test_realtime_process),
            cmocka_unit_test(test_realtime_process_len),
            cmocka_unit_test(test_realtime_process_failure),
        #endif
    };

    return cmocka_run_group_tests(tests, setup_group, teardown_group);
}