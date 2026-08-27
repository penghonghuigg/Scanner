import { mount } from '@vue/test-utils'

import App from '../App.vue'
import { BRANCH_VALUES, ROLE_VALUES } from '../types/auth'

test('认证角色与后端契约一致', () => {
  expect(ROLE_VALUES).toEqual(['ADMIN', 'OPERATOR', 'VIEWER'])
})

test('分局代码与批准设计一致', () => {
  expect(BRANCH_VALUES).toEqual(['TIANDA', 'XIEBA', 'PANJI', 'SHOUXIAN', 'FENGTAI'])
})

test('应用外壳保留路由视图', () => {
  const wrapper = mount(App, {
    global: { stubs: { RouterView: { template: '<main data-router-view />' } } },
  })
  expect(wrapper.find('[data-router-view]').exists()).toBe(true)
})
