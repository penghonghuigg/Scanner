import { createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

import LoginView from '../views/LoginView.vue'

test('登录页包含品牌区、账号密码输入与登录按钮', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: LoginView }],
  })
  await router.push('/')
  await router.isReady()
  const wrapper = mount(LoginView, {
    global: {
      plugins: [createPinia(), router],
    },
  })

  expect(wrapper.text()).toContain('涉案卷烟智能统计系统')
  expect(wrapper.text()).toContain('账号登录')
  expect(wrapper.find('input[name="username"]').exists()).toBe(true)
  expect(wrapper.find('input[name="password"]').attributes('type')).toBe('password')
  expect(wrapper.find('button[type="submit"]').text()).toContain('登录系统')
})
