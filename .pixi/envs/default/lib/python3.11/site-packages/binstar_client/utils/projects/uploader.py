# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

import tqdm

import binstar_client
from binstar_client.utils import compute_hash, jencode
from binstar_client.utils.multipart_uploader import multipart_files_upload


class ProjectUploader(binstar_client.Binstar):
    def __init__(self, token, **kwargs):
        domain = kwargs.get('domain', 'https://api.anaconda.org')
        verify = kwargs.get('verify', True)
        self.username = kwargs.get('username', None)
        self.project = kwargs.get('project', None)
        super().__init__(token, domain, verify)

    def exists(self):
        url = '{}/apps/{}/projects/{}'.format(
            self.domain, self.username, self.project.name)
        res = self.session.get(url)
        return res.status_code == 200

    def create(self):
        url = '{}/apps/{}/projects'.format(self.domain, self.username)
        data, headers = jencode(self.project.to_project_creation())
        res = self.session.post(url, data=data, headers=headers)
        return res

    def stage(self):
        url = '{}/apps/{}/projects/{}/stage'.format(
            self.domain, self.username, self.project.name)
        data, headers = jencode(self.project.to_stage())
        res = self.session.post(url, data=data, headers=headers)
        self._check_response(res)
        return res

    def commit(self, revision_id):
        url = '{}/apps/{}/projects/{}/commit/{}'.format(
            self.domain, self.username,
            self.project.name, revision_id
        )
        data, headers = jencode({})
        res = self.session.post(url, data=data, headers=headers)
        self._check_response(res, [201])
        return res

    def file_upload(self, url, obj):
        _hexmd5, b64md5, size = compute_hash(
            self.project.tar, size=self.project.size)

        s3data = obj['form_data']
        s3data['Content-Length'] = str(size)
        s3data['Content-MD5'] = b64md5

        with tqdm.tqdm(total=size, unit='B', unit_scale=True, unit_divisor=1024) as progress:
            s3res = multipart_files_upload(
                url,
                data=s3data,
                files={'file': (self.project.basename, self.project.tar)},
                progress_bar=progress,
                verify=self.session.verify)

        if s3res.status_code != 201:
            raise binstar_client.errors.BinstarError(
                'Error uploading package', s3res.status_code)
        return s3res

    def projects(self):
        url = '{}/apps/{}/projects'.format(self.domain, self.username)
        data, headers = jencode(self.project.to_project_creation())
        return self.session.get(url, data=data, headers=headers)

    def upload(self):  # pylint: disable=arguments-differ
        """
        * Check if project already exists
            * if it doesn't, then create it
        * stage a new revision
        * upload
        * commit revision
        """
        if not self.exists():
            self.create()

        data = self.stage().json()
        self.file_upload(data['post_url'], data)
        res = self.commit(data['dist_id'])
        data = res.json()
        return data
