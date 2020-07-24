# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from app.auth.routes import oauth
from tests.conftest import as_user
from tests.conftest import regular_user_info
from tests.conftest import set_user


def test_authenticated_users_get_redirected_to_home(app, client_without_db):
    client = client_without_db
    with set_user(app, as_user(client)):
        with app.app_context():
            resp = client.get('/auth/login')
            assert resp.status_code == 302
            assert resp.headers.get('Location') == 'http://localhost/'


def test_unauthenticated_users_can_choose_login(client_without_db):
    client = client_without_db
    resp = client.get('/auth/login')
    assert resp.status_code == 200
    assert b'fetch_profile' in resp.data
    assert b'Sign in with Google' in resp.data


def test_users_get_redirected_to_minimal_oauth_consent_screen_by_default(
    client_without_db):
    client = client_without_db
    resp = client.get('/auth/login?as_user=OAuth')
    assert resp.status_code == 302
    target = resp.headers.get('Location')
    assert target.startswith('https://accounts.google.com/o/oauth2/v2/auth')
    assert 'profile' not in target

    resp = client.post('/auth/login?as_user=OAuth')
    assert resp.status_code == 302
    target = resp.headers.get('Location')
    assert target.startswith('https://accounts.google.com/o/oauth2/v2/auth')
    assert 'profile' not in target

    resp = client.post('/auth/login?as_user=OAuth',
                       data={'fetch_profile': 'false'})
    assert resp.status_code == 302
    target = resp.headers.get('Location')
    assert target.startswith('https://accounts.google.com/o/oauth2/v2/auth')
    assert 'profile' not in target


def test_users_get_redirected_to_full_oauth_consent_screen_with_optin(
    client_without_db):
    client = client_without_db
    resp = client.post('/auth/login?as_user=OAuth',
                       data={'fetch_profile': 'true'})
    assert resp.status_code == 302
    target = resp.headers.get('Location')
    assert target.startswith('https://accounts.google.com/o/oauth2/v2/auth')
    assert 'profile' in target


def test_logout_clears_the_session(app, client_without_db):
    client = client_without_db

    with set_user(app, as_user(client)):
        with app.app_context():
            with client.session_transaction() as session:
                session['something_else'] = True
            # request /maintenance as it doesn't use the database
            resp = client.get('/maintenance')
            assert resp.status_code == 200
            with client.session_transaction() as session:
                assert 'user_info' in session
                assert 'something_else' in session

            resp = client.get('/auth/logout')
            assert resp.status_code == 302
            assert resp.headers.get('Location') == 'http://localhost/'
            with client.session_transaction() as session:
                assert 'user_info' not in session
                assert 'something_else' not in session


def test_authorization_callback_success(mocker, client_without_db):
    client = client_without_db
    mocker.patch('app.auth.routes.oauth.google.authorize_access_token')
    mocker.patch('app.auth.routes.oauth.google.get')

    oauth.google.authorize_access_token.return_value = {
        'access_token': 'TOKEN'
    }

    class Resp:
        def json(self):
            return regular_user_info()

    oauth.google.get.return_value = Resp()

    resp = client.get('/auth/authorized')

    assert resp.status_code == 302
    assert resp.headers.get('Location') == 'http://localhost/'

    assert oauth.google.authorize_access_token.called_once()
    assert oauth.google.get.called_once_with("getuserinfo", token='TOKEN')
    with client.session_transaction() as session:
        assert 'user_info' in session


# TODO: Re-enable this test.
# def test_authorization_callback_access_denied(mocker, client_without_db):
#     client = client_without_db
#     mocker.patch('app.auth.routes.oauth.google.authorize_access_token')
#     mocker.patch('app.auth.routes.oauth.google.get')
#     oauth.google.authorize_access_token.return_value = None
#
#     resp = client.get('/auth/authorized')
#
#     #assert resp.status_code == 200
#     #assert b'Access denied' in resp.data
#
#     assert oauth.google.authorize_access_token.called_once()
#     with client.session_transaction() as session:
#         assert 'user_info' not in session


def test_authorization_callback_access_denied_with_reason(
    mocker, client_without_db):
    client = client_without_db
    mocker.patch('app.auth.routes.oauth.google.authorize_access_token')
    mocker.patch('app.auth.routes.oauth.google.get')
    oauth.google.authorize_access_token.return_value = None

    resp = client.get(
        '/auth/authorized?error_reason=testing_unauthenticated&error_description=just+testing'
    )

    assert resp.status_code == 200
    assert b'Access denied' in resp.data
    assert b'testing_unauthenticated' in resp.data
    assert b'just testing' in resp.data

    assert oauth.google.authorize_access_token.called_once()
    with client.session_transaction() as session:
        assert 'user_info' not in session


def test_authorization_callback_redirect(mocker, client_without_db):
    client = client_without_db
    mocker.patch('app.auth.routes.oauth.google.authorize_access_token')
    mocker.patch('app.auth.routes.oauth.google.get')

    oauth.google.authorize_access_token.return_value = {
        'access_token': 'TOKEN'
    }

    class Resp:
        def json(self):
            return regular_user_info()

    oauth.google.get.return_value = Resp()

    with client.session_transaction() as session:
        session['redirect_path'] = '/FOO'

    resp = client.get('/auth/authorized')

    assert resp.status_code == 302
    assert resp.headers.get('Location') == 'http://localhost/FOO'

    assert oauth.google.authorize_access_token.called_once()
    assert oauth.google.get.called_once_with("getuserinfo", token='TOKEN')
    with client.session_transaction() as session:
        assert 'user_info' in session
        assert 'redirect_path' not in session
